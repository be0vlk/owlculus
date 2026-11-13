import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { mountWithVuetify } from './helpers/vuetify'
import StrixyChat from '@/views/StrixyChat.vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import api from '@/services/api'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}))
let wrapper, history, transcript
const base = '/api/strixy/cases/2/conversations'
beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  const active = useActiveCaseStore()
  Object.assign(active, { initialized: true, accessibleCases: [{ id: 2, case_number: 'CASE-2' }] })
  active.resolve(2)
  history = []
  transcript = { messages: [], runs: [] }
  api.get.mockImplementation(async (url) => ({
    data: url.endsWith('availability')
      ? { is_configured: true }
      : url.endsWith('/shares')
        ? []
        : url === base
          ? history
          : transcript,
  }))
  api.post.mockImplementation(async (url) => ({
    data: url === base ? { id: 'one' } : { id: 'run', status: 'completed' },
  }))
})
afterEach(() => wrapper?.unmount())
async function mountChat() {
  wrapper = mountWithVuetify({
    components: { StrixyChat },
    template: '<v-app><StrixyChat /></v-app>',
  })
  await flushPromises()
}
it('starts a new conversation from a prompt without opening a menu', async () => {
  await mountChat()
  expect(wrapper.text()).toContain('Where should we start?')
  expect(wrapper.text()).not.toContain('Focus on records')
  await wrapper.findAll('.strixy-starters button')[0].trigger('click')
  await flushPromises()
  expect(api.post).toHaveBeenCalledWith(base)
  expect(api.post).toHaveBeenCalledWith(`${base}/one/messages`, {
    content: 'Give me a quick briefing on this case.',
  })
})
it('uses the active case without loading a record catalog or asking for scope', async () => {
  await mountChat()
  expect(wrapper.find('[aria-label="Choose sources"]').exists()).toBe(false)
  expect(wrapper.find('select, [role="combobox"]').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('Entire case')
  expect(api.get.mock.calls.some(([url]) => url.endsWith('/sources'))).toBe(false)
  expect(api.get).toHaveBeenCalledWith(base)
  await wrapper.get('[aria-label="Message input"]').setValue('Which employees share an address?')
  await wrapper.get('[aria-label="Send message"]').trigger('submit')
  await flushPromises()
  expect(api.post).toHaveBeenCalledWith(`${base}/one/messages`, {
    content: 'Which employees share an address?',
  })
})
it('keeps Shift+Enter and IME composition from submitting a draft', async () => {
  await mountChat()
  const input = wrapper.get('[aria-label="Message input"]')
  await input.setValue('Two lines')
  await input.trigger('keydown', { key: 'Enter', shiftKey: true })
  await input.trigger('keydown', { key: 'Enter', isComposing: true })
  expect(api.post).not.toHaveBeenCalled()
  await input.trigger('keydown', { key: 'Enter' })
  await flushPromises()
  expect(api.post).toHaveBeenCalledWith(`${base}/one/messages`, { content: 'Two lines' })
})
it('refreshes and searches named history before reopening its transcript', async () => {
  await mountChat()
  history = [{ id: 'one', title: 'Who is Ada?', created_at: '2026-09-12T12:00:00Z' }]
  transcript = {
    messages: [
      { id: 'question', role: 'user', content: 'Who is Ada?', timestamp: '2026-09-12T12:00:00Z' },
    ],
    runs: [],
  }
  await wrapper.get('[aria-label="Conversations"]').trigger('click')
  await flushPromises()
  const dialog = new DOMWrapper(document.body).get('[role="dialog"]')
  expect(dialog.text()).toContain('Who is Ada?')
  await dialog.find('input[type="text"]').setValue('Ada')
  await dialog
    .find('.v-field__clearable button, .v-field__clearable [role="button"]')
    .trigger('click')
  await flushPromises()
  expect(dialog.text()).toContain('Who is Ada?')
  await dialog.find('.v-list-item').trigger('click')
  await flushPromises()
  expect(api.get).toHaveBeenCalledWith(`${base}/one`)
  expect(wrapper.find('.user-message').text()).toContain('Who is Ada?')
})
it('keeps the conversation and raises no error when deletion is cancelled', async () => {
  const rejections = []
  const onRejection = (reason) => rejections.push(reason)
  globalThis.process.on('unhandledRejection', onRejection)
  history = [{ id: 'one', title: 'Who is Ada?', created_at: '2026-09-12T12:00:00Z' }]
  await mountChat()
  const body = new DOMWrapper(document.body)
  await wrapper.get('[aria-label="Conversation actions"]').trigger('click')
  await flushPromises()
  await body
    .findAll('.v-list-item')
    .find((item) => item.text() === 'Delete conversation')
    .trigger('click')
  await flushPromises()
  await body
    .get('[aria-label="Delete conversation"]')
    .findAll('button')
    .find((button) => button.text() === 'Cancel')
    .trigger('click')
  await flushPromises()
  globalThis.process.off('unhandledRejection', onRejection)
  expect(api.delete).not.toHaveBeenCalled()
  expect(rejections).toEqual([])
})
