import { beforeEach, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useStrixyChat } from '../useStrixyChat'
import { useActiveCaseStore } from '../../stores/activeCase'
import api from '../../services/api'
import { systemService } from '../../services/system'

vi.mock('../../services/api', () => ({ default: { post: vi.fn() } }))
vi.mock('../../services/system', () => ({
  systemService: { checkApiKeyStatus: vi.fn().mockResolvedValue({ is_configured: true }) },
}))
vi.mock('../useNotifications', () => ({ useNotifications: () => ({ showError: vi.fn() }) }))

let scope
let chat
let activeCase
beforeEach(() => {
  scope?.stop()
  vi.clearAllMocks()
  setActivePinia(createPinia())
  activeCase = useActiveCaseStore()
  Object.assign(activeCase, { initialized: true, accessibleCases: [{ id: 1 }, { id: 2 }] })
  activeCase.resolve(2)
  scope = effectScope()
  chat = scope.run(() => useStrixyChat())
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

it('allows investigators to chat when the administrator-only key status is forbidden', async () => {
  systemService.checkApiKeyStatus.mockRejectedValueOnce({ response: { status: 403 } })
  await chat.initializeChat()
  api.post.mockResolvedValueOnce({ data: { message: 'Investigator reply' } })
  chat.currentMessage.value = 'An assigned case question'
  await chat.sendMessage()
  expect(chat.apiKeyError.value).toBe(false)
  expect(chat.messages.value.at(-1).content).toBe('Investigator reply')
})
