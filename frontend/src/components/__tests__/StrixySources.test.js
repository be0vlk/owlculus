import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { mountWithVuetify } from './helpers/vuetify'
import StrixyChat from '@/views/StrixyChat.vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import api from '@/services/api'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
let wrapper
const citation = {
  source_id: 'entity:7',
  field: 'data',
  excerpt: 'Ada',
  inspected_at: '2026-01-01T12:00:00Z',
  source_status: 'changed',
}
afterEach(() => {
  wrapper?.unmount()
  vi.clearAllMocks()
})

it('shows coverage, changed-source citations and authorized previews without model links', async () => {
  setActivePinia(createPinia())
  const active = useActiveCaseStore()
  Object.assign(active, { initialized: true, accessibleCases: [{ id: 2, case_number: 'CASE-2' }] })
  active.resolve(2)
  api.get.mockImplementation(async (url) => ({
    data: url.endsWith('availability')
      ? { is_configured: true }
      : url.endsWith('conversations')
        ? [{ id: 'one' }]
        : url.endsWith('entity%3A7')
          ? { sources: [{ source_id: 'entity:7', fields: { data: 'Ada in current record' } }] }
          : {
              messages: [
                {
                  role: 'assistant',
                  content:
                    '[Untrusted](https://untrusted.invalid) ![Image](https://untrusted.invalid/a.png)',
                  timestamp: '2026-01-01T12:00:00Z',
                  citations: [citation],
                  source_labels: { 'entity:7': { title: 'Ada Lovelace', subtitle: 'Person' } },
                  coverage: {
                    mode: 'broad',
                    complete: false,
                    enumeration_complete: false,
                    counts: { read: 1, partly_read: 2, unexamined: 3 },
                  },
                },
              ],
              runs: [],
            },
  }))
  wrapper = mountWithVuetify({
    components: { StrixyChat },
    template: '<v-app><StrixyChat /></v-app>',
  })
  await flushPromises()
  expect(wrapper.text()).toContain('Some records or attachments were not fully reviewed.')
  expect(wrapper.text()).toContain('Source changed since this answer.')
  expect(wrapper.find('.message-content a').exists()).toBe(false)
  expect(wrapper.find('.message-content img').exists()).toBe(false)
  const button = wrapper.find('[aria-label="Open source 1: Ada Lovelace"]')
  await button.trigger('click')
  await flushPromises()
  const body = new DOMWrapper(document.body)
  const dialog = body.find('[role="dialog"]')
  expect(dialog.text()).toContain('Ada in current record')
  expect(api.get.mock.calls.some(([url]) => url.endsWith('/sources'))).toBe(false)
  await dialog
    .findAll('button')
    .find((button) => button.text() === 'Ask about this')
    .trigger('click')
  expect(wrapper.get('[aria-label="Message input"]').element.value).toBe(
    'What does Ada Lovelace tell us?',
  )
  api.post.mockResolvedValue({ data: { id: 'run', status: 'completed' } })
  await wrapper.get('[aria-label="Send message"]').trigger('submit')
  await flushPromises()
  expect(api.post).toHaveBeenCalledWith('/api/strixy/cases/2/conversations/one/messages', {
    content: 'What does Ada Lovelace tell us?',
  })
})

it('distinguishes examined attachment lines from partial and unavailable attachments', async () => {
  setActivePinia(createPinia())
  const active = useActiveCaseStore()
  Object.assign(active, { initialized: true, accessibleCases: [{ id: 2, case_number: 'CASE-2' }] })
  active.resolve(2)
  api.get.mockImplementation(async (url) => ({
    data: url.endsWith('availability')
      ? { is_configured: true }
      : url.endsWith('conversations')
        ? [{ id: 'one' }]
        : {
            messages: [
              {
                role: 'assistant',
                content: 'Partial document findings',
                source_labels: { 'evidence:8': { title: 'Collected PDF', subtitle: 'Evidence' } },
                timestamp: '2026-01-01T12:00:00Z',
                citations: [
                  {
                    ...citation,
                    source_id: 'evidence:8',
                    field: 'attachment:page:2:image',
                    kind: 'visual',
                    excerpt: '',
                  },
                ],
                coverage: {
                  mode: 'broad',
                  complete: false,
                  enumeration_complete: true,
                  counts: { read: 1, partly_read: 1, unexamined: 0 },
                  attachment_outcomes: [
                    {
                      source_id: 'evidence:8',
                      state: 'partly_read',
                      reason: 'attachment_unit_limit',
                      units_read: 2,
                      total_units: 4,
                      unexamined_from: 3,
                      pages: [
                        { unit: 1, state: 'read' },
                        { unit: 2, state: 'unavailable', reason: 'unreadable_page' },
                      ],
                    },
                    {
                      source_id: 'evidence:9',
                      state: 'unavailable',
                      reason: 'encrypted_file',
                      units_read: 0,
                    },
                    { source_id: 'evidence:10', state: 'read', units_read: 3 },
                  ],
                },
              },
            ],
            runs: [],
          },
  }))
  wrapper = mountWithVuetify({
    components: { StrixyChat },
    template: '<v-app><StrixyChat /></v-app>',
  })
  await flushPromises()
  expect(wrapper.text()).toContain('Some records or attachments were not fully reviewed.')
  expect(wrapper.text()).not.toContain('Attachment unit limit reached')
  await wrapper.find('.review-button').trigger('click')
  await flushPromises()
  const review = new DOMWrapper(document.body).find('[role="dialog"]')
  expect(review.text()).toContain('Collected PDF: Attachment partly examined')
  expect(review.text()).toContain('Attachment unit limit reached')
  expect(review.text()).toContain('File is encrypted')
  expect(review.text()).toContain('Evidence #10: Attachment examined')
  expect(review.text()).toContain('Page 2')
  expect(review.text()).toContain('Pages 3–4 unexamined')
  expect(review.text()).toContain('This page could not be rendered faithfully')
  expect(review.text()).toContain(
    'Visual reference; interpretation is not a verified transcription',
  )
  await review.find('[aria-label="Close review details"]').trigger('click')
  await flushPromises()
  api.get.mockResolvedValueOnce({
    data: {
      sources: [{ source_id: 'evidence:8', fields: { title: 'Current PDF' } }],
      images: [{ source_id: 'evidence:8', field: 'attachment:page:2:image', data: 'cGl4ZWxz' }],
    },
  })
  await wrapper
    .findAll('button')
    .find((b) => b.text().includes('Collected PDF'))
    .trigger('click')
  await flushPromises()
  expect(api.get).toHaveBeenLastCalledWith('/api/strixy/cases/2/sources/evidence%3A8', {
    params: { unit: 2 },
  })
  const dialog = new DOMWrapper(document.body).find(
    '[role="dialog"][aria-labelledby="strixy-preview-title"]',
  )
  expect(dialog.text()).toContain('Current file shown')
  expect(dialog.find('img').attributes('src')).toBe('data:image/png;base64,cGl4ZWxz')
  expect(wrapper.text()).not.toContain('Attachments unexamined.')
})
