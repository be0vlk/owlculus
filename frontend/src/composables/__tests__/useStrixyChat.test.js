import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useStrixyChat } from '../useStrixyChat'
import { useActiveCaseStore } from '../../stores/activeCase'
import api from '../../services/api'

vi.mock('../../services/api', () => ({ default: { post: vi.fn(), get: vi.fn(), delete: vi.fn() } }))
let scope, chat, activeCase, saved
const detail = '/api/strixy/cases/2/conversations/one'
beforeEach(async () => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  activeCase = useActiveCaseStore()
  Object.assign(activeCase, { initialized: true, accessibleCases: [{ id: 1 }, { id: 2 }] })
  activeCase.resolve(2)
  saved = { messages: [], runs: [] }
  api.get.mockImplementation(async (url) => ({
    data: url.endsWith('availability')
      ? { is_configured: true }
      : url.endsWith('conversations')
        ? [{ id: 'one' }]
        : saved,
  }))
  scope = effectScope()
  chat = scope.run(() => useStrixyChat())
  await chat.initializeChat()
})
afterEach(() => scope.stop())

it('submits only a new message and displays persisted timestamps', async () => {
  saved = {
    messages: [
      { role: 'user', content: 'Question', timestamp: '2026-01-01T12:00:00' },
      { role: 'assistant', content: 'Saved reply', timestamp: '2026-01-01T12:01:00' },
    ],
    runs: [{ id: 'run', status: 'completed' }],
  }
  api.post.mockResolvedValue({ data: saved.runs[0] })
  chat.currentMessage.value = 'Question'
  await chat.sendMessage()
  expect(api.post).toHaveBeenCalledWith(`${detail}/messages`, { content: 'Question' })
  expect(chat.messages.value).toEqual(saved.messages)
  expect(chat.currentMessage.value).toBe('')
})

it('reopens pending work and polls authoritative output without duplicates', async () => {
  vi.useFakeTimers()
  saved = {
    messages: [{ role: 'user', content: 'Question' }],
    runs: [{ id: 'run', status: 'running' }],
  }
  await chat.selectConversation('one')
  expect(chat.loading.value).toBe(true)
  saved = {
    messages: [...saved.messages, { role: 'assistant', content: 'Answer' }],
    runs: [{ id: 'run', status: 'completed' }],
  }
  await vi.advanceTimersByTimeAsync(1000)
  expect(chat.messages.value).toEqual(saved.messages)
  expect(chat.loading.value).toBe(false)
  vi.useRealTimers()
})

it('preserves old conversations when creating a new one', async () => {
  api.post.mockResolvedValue({ data: { id: 'two' } })
  await chat.createConversation()
  expect(chat.conversations.value.map((c) => c.id)).toEqual(['two', 'one'])
  expect(chat.conversationId.value).toBe('two')
})

it('discards late responses when switching cases and returning', async () => {
  let finish
  api.post.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  chat.currentMessage.value = 'Private question'
  const pending = chat.sendMessage()
  activeCase.resolve(1)
  activeCase.resolve(2)
  finish({ data: { id: 'late', status: 'running' } })
  await pending
  expect(chat.currentMessage.value).toBe('')
  expect(chat.latestRun.value?.id).not.toBe('late')
})

it('clears protected content after assignment revocation', async () => {
  saved.messages = [{ content: 'Private answer' }]
  await chat.selectConversation('one')
  api.get.mockRejectedValueOnce({
    response: {
      status: 403,
      data: { code: 'strixy_not_assigned', detail: 'Ask an administrator to assign Strixy.' },
    },
  })
  await chat.initializeChat()
  expect(chat.canChat.value).toBe(false)
  expect(chat.messages.value).toEqual([])
  expect(activeCase.activeCaseId).toBe(2)
})

it('keeps failed submissions as drafts and requires an explicit retry', async () => {
  api.post.mockRejectedValueOnce(new Error('network lost'))
  chat.currentMessage.value = 'My draft'
  await chat.sendMessage()
  expect(chat.currentMessage.value).toBe('My draft')
  expect(chat.operationError.value).toContain('check whether your message was accepted')
  expect(api.post).toHaveBeenCalledTimes(1)
})

it('deletes the selected conversation and clears the transcript', async () => {
  api.delete.mockResolvedValue({})
  await chat.deleteConversation()
  expect(api.delete).toHaveBeenCalledWith(detail)
  expect(chat.conversations.value).toEqual([])
  expect(chat.messages.value).toEqual([])
})

it('loads a replacement Case after a background access refresh finishes', async () => {
  activeCase.refreshing = true
  activeCase.resolve(1)
  expect(chat.canChat.value).toBe(false)
  activeCase.refreshing = false
  await new Promise((resolve) => setTimeout(resolve, 0))
  expect(chat.canChat.value).toBe(true)
  expect(api.get).toHaveBeenCalledWith('/api/strixy/cases/1/conversations')
})

it('automatically sends subsequent questions in the newly active case', async () => {
  api.post.mockResolvedValue({ data: { id: 'run', status: 'completed' } })
  chat.currentMessage.value = 'Compare the employees'
  await chat.sendMessage()
  expect(api.post).toHaveBeenLastCalledWith(`${detail}/messages`, {
    content: 'Compare the employees',
  })
  activeCase.resolve(1)
  await flushPromises()
  chat.currentMessage.value = 'Summarize this case'
  await chat.sendMessage()
  expect(api.post).toHaveBeenLastCalledWith('/api/strixy/cases/1/conversations/one/messages', {
    content: 'Summarize this case',
  })
  expect(api.get.mock.calls.some(([url]) => url.endsWith('/sources'))).toBe(false)
})

it('does not restore a stale history title after switching cases', async () => {
  let finish
  api.get.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const pending = chat.refreshConversations()
  activeCase.resolve(1)
  finish({ data: [{ id: 'old', title: 'Private old case question' }] })
  await pending
  expect(chat.conversations.value.some((item) => item.title === 'Private old case question')).toBe(
    false,
  )
})

it('discards a late citation preview after switching Cases', async () => {
  let finish
  api.get.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const pending = chat.openSource({ source_id: 'entity:7' })
  activeCase.resolve(1)
  finish({ data: { sources: [{ source_id: 'entity:7', fields: { data: 'Private' } }] } })
  await pending
  expect(chat.sourcePreview.value).toBe(null)
})

it('revalidates a saved answer before export and drops revoked text', async () => {
  chat.messages.value = [{ role: 'assistant', content: 'Previously visible' }]
  saved = { case_id: 2, messages: [{ role: 'assistant', content: '', withheld: true }], runs: [] }
  const exported = await chat.authorizedExport()
  expect(exported.messages[0].withheld).toBe(true)
  expect(JSON.stringify(exported)).not.toContain('Previously visible')
  expect(chat.messages.value).toEqual(saved.messages)
})

it('recovers streamed findings, cancels owned work and explicitly continues', async () => {
  saved = {
    messages: [{ id: 'question', position: 0, role: 'user', content: 'Question' }],
    runs: [
      {
        id: 'run',
        position: 0,
        status: 'running',
        progress: 'preparing_findings',
        partial: { id: 'run', content: 'Partial finding', role: 'assistant' },
      },
    ],
  }
  await chat.selectConversation('one')
  expect(chat.visibleMessages.value.map((message) => message.content)).toEqual([
    'Question',
    'Partial finding',
  ])
  saved.runs[0].status = 'cancelled'
  api.post.mockResolvedValue({ data: saved.runs[0] })
  await chat.controlRun('cancel')
  expect(api.post).toHaveBeenCalledWith(`${detail}/runs/run/cancel`)
  saved.runs.push({ id: 'continued', position: 1, status: 'pending' })
  await chat.controlRun('continue')
  expect(api.post).toHaveBeenLastCalledWith(`${detail}/runs/run/continue`)
})

it('does not let an older poll restore running output after cancellation', async () => {
  vi.useFakeTimers()
  try {
    saved = { messages: [], runs: [{ id: 'run', status: 'running' }] }
    await chat.selectConversation('one')
    let finishPoll
    api.get.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishPoll = resolve
        }),
    )
    await vi.advanceTimersByTimeAsync(1000)
    saved = { messages: [], runs: [{ id: 'run', status: 'cancelled' }] }
    api.post.mockResolvedValue({ data: saved.runs[0] })
    await chat.controlRun('cancel')
    finishPoll({ data: { messages: [], runs: [{ id: 'run', status: 'running' }] } })
    await flushPromises()
    expect(chat.latestRun.value.status).toBe('cancelled')
  } finally {
    vi.useRealTimers()
  }
})

it('keeps a late shared snapshot out of a newly selected Case', async () => {
  let finish
  api.get.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const pending = chat.openShare('shared')
  activeCase.resolve(1)
  finish({ data: { id: 'shared', messages: [{ content: 'Other Case secret' }] } })
  await pending
  expect(chat.sharedSnapshot.value).toBeNull()
  expect(chat.visibleMessages.value.some((m) => m.content === 'Other Case secret')).toBe(false)
})

it('opens fixed read-only content and creates an independent private follow-up', async () => {
  api.get.mockResolvedValueOnce({ data: { id: 'shared', messages: [{ content: 'Fixed answer' }] } })
  await chat.openShare('shared')
  expect(chat.canChat.value).toBe(false)
  expect(chat.visibleMessages.value).toEqual([{ content: 'Fixed answer' }])
  api.post.mockResolvedValueOnce({ data: { id: 'copy' } })
  await chat.copyShare()
  expect(api.post).toHaveBeenCalledWith('/api/strixy/cases/2/shares/shared/copy')
  expect(chat.conversationId.value).toBe('copy')
  expect(chat.sharedSnapshot.value).toBeNull()
})
