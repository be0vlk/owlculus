import { beforeEach, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useStrixyChat } from '../useStrixyChat'
import { useActiveCaseStore } from '../../stores/activeCase'
import api from '../../services/api'

vi.mock('../../services/api', () => ({ default: { post: vi.fn(), get: vi.fn() } }))
vi.mock('../useNotifications', () => ({ useNotifications: () => ({ showError: vi.fn() }) }))

let scope
let chat
let activeCase
beforeEach(async () => {
  scope?.stop()
  vi.clearAllMocks()
  setActivePinia(createPinia())
  activeCase = useActiveCaseStore()
  Object.assign(activeCase, { initialized: true, accessibleCases: [{ id: 1 }, { id: 2 }] })
  activeCase.resolve(2)
  scope = effectScope()
  chat = scope.run(() => useStrixyChat())
  api.get.mockResolvedValue({ data: { is_configured: true } })
  await chat.checkAvailability()
})

it('sends only conversation messages and the resolved active case', async () => {
  api.post.mockResolvedValue({ data: { message: 'Reply for case two' } })
  chat.currentMessage.value = 'Investigate this domain'
  await chat.sendMessage()
  expect(api.post).toHaveBeenCalledWith('/api/strixy/chat', {
    case_id: 2,
    messages: [{ role: 'user', content: 'Investigate this domain' }],
  })
  expect(chat.messages.value.at(-1).content).toBe('Reply for case two')
})

it('blocks sends while context is unresolved or refreshing', async () => {
  for (const state of [
    { initialized: false },
    { initialized: true, refreshing: true },
    { refreshing: false, accessibleCases: [] },
  ]) {
    Object.assign(activeCase, state)
    chat.currentMessage.value = 'Do not send'
    await chat.sendMessage()
  }
  expect(api.post).not.toHaveBeenCalled()
})

it('drops drafts and late replies when switching investigations, even when returning', async () => {
  let finish
  api.post.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  chat.currentMessage.value = 'Private question for case two'
  const pending = chat.sendMessage()
  activeCase.resolve(1)
  chat.currentMessage.value = 'Draft for case one'
  activeCase.resolve(2)
  finish({ data: { message: 'Late reply for the old conversation' } })
  await pending
  expect(chat.currentMessage.value).toBe('')
  expect(chat.messages.value.some((message) => /Private|Late|Draft/.test(message.content))).toBe(
    false,
  )
  expect(chat.loading.value).toBe(false)
})

it('explains missing AI assignment without discarding the accessible active case', async () => {
  api.get.mockRejectedValueOnce({
    response: {
      status: 403,
      data: {
        code: 'strixy_not_assigned',
        detail: 'Strixy is not assigned to this case. Ask an administrator to assign Strixy.',
      },
    },
  })
  await chat.checkAvailability()
  expect(chat.availabilityError.value).toContain('not assigned')
  expect(activeCase.activeCaseId).toBe(2)
  chat.currentMessage.value = 'Do not send'
  await chat.sendMessage()
  expect(api.post).not.toHaveBeenCalled()
  await chat.checkAvailability()
  expect(chat.availabilityError.value).toBe('')
  api.post.mockResolvedValueOnce({ data: { message: 'Now assigned' } })
  await chat.sendMessage()
  expect(chat.messages.value.at(-1).content).toBe('Now assigned')
})

it('handles membership revocation between availability check and send', async () => {
  api.post.mockRejectedValueOnce({
    response: {
      status: 403,
      data: {
        code: 'strixy_not_assigned',
        detail: 'Strixy is not assigned to this case. Ask an administrator to assign Strixy.',
      },
    },
  })
  chat.currentMessage.value = 'Question'
  await chat.sendMessage()
  expect(chat.availabilityError.value).toContain('not assigned')
  expect(activeCase.activeCaseId).toBe(2)
})

it('keeps the active case when the server changes the assignment explanation', async () => {
  api.get.mockRejectedValueOnce({
    response: {
      status: 403,
      data: {
        code: 'strixy_not_assigned',
        detail: 'Ask your administrator to add the AI Analyst.',
      },
    },
  })
  await chat.checkAvailability()
  expect(chat.availabilityError.value).toBe('Ask your administrator to add the AI Analyst.')
  expect(activeCase.activeCaseId).toBe(2)
})
