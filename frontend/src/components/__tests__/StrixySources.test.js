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
        : url.endsWith('/sources')
          ? { sources: [{ source_id: 'entity:7' }] }
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
  expect(wrapper.text()).toContain('Incomplete coverage.')
  expect(wrapper.text()).toContain('Source changed since this answer.')
  expect(wrapper.find('.message-content a').exists()).toBe(false)
  expect(wrapper.find('.message-content img').exists()).toBe(false)
  const button = wrapper.findAll('button').find((b) => b.text().includes('entity:7'))
  await button.trigger('click')
  await flushPromises()
  const body = new DOMWrapper(document.body)
  expect(body.find('[role="dialog"]').text()).toContain('Ada in current record')
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
        : url.endsWith('/sources')
          ? { sources: [] }
          : {
              messages: [
                {
                  role: 'assistant',
                  content: 'Partial document findings',
                  timestamp: '2026-01-01T12:00:00Z',
                  citations: [
                    {
                      ...citation,
                      source_id: 'evidence:8',
                      field: 'attachment:sheet:Witnesses:row:2',
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
  expect(wrapper.text()).toContain('evidence:8: Attachment partly examined')
  expect(wrapper.text()).toContain('Attachment unit limit reached')
  expect(wrapper.text()).toContain('File is encrypted')
  expect(wrapper.text()).toContain('evidence:10: Attachment examined')
  expect(wrapper.text()).toContain('attachment:sheet:Witnesses:row:2')
  expect(wrapper.text()).not.toContain('Attachments unexamined.')
})
