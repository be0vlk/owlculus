import { expect, it, vi } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import { VForm } from 'vuetify/components'
import CorrelationScanPluginResult from '../plugins/CorrelationScanPluginResult.vue'
import GenericPluginParams from '../plugins/GenericPluginParams.vue'
import PluginResultsModal from '../plugins/PluginResultsModal.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

vi.mock('@/composables/usePluginApiKeys', () => ({
  usePluginApiKeys: () => ({ checkPluginApiKeys: vi.fn(), getMissingApiKeys: () => [] }),
}))

it('validates generic required fields without rendering plugin metadata as inputs', async () => {
  const wrapper = mountWithVuetify(VForm, {
    slots: {
      default: {
        components: { GenericPluginParams },
        template: `<GenericPluginParams :model-value="{}" :parameters="{ query: { type: 'string', required: true, label: 'Search query' }, api_key_requirements: [] }" />`,
      },
    },
  })
  await flushPromises()
  expect(wrapper.findAll('input')).toHaveLength(1)
  expect((await wrapper.vm.validate()).valid).toBe(false)
  expect(wrapper.text()).toContain('Search query is required')
  await wrapper.get('input').setValue('example.org')
  expect((await wrapper.vm.validate()).valid).toBe(true)
})

it('shows structured results, exports them, and closes through an accessible action', async () => {
  const wrapper = mountWithVuetify(PluginResultsModal, {
    props: {
      modelValue: false,
      pluginName: 'ExamplePlugin',
      results: { matches: ['example.org'] },
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('example.org')
  await dialog
    .findAll('button')
    .find((button) => button.text().includes('Export'))
    .trigger('click')
  expect(wrapper.emitted('export')[0][0].results).toEqual({ matches: ['example.org'] })
  await dialog.get('button[aria-label="Close plugin results"]').trigger('click')
  expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
})

it.each([[], {}, null])('shows an explicit empty result state for %j', async (results) => {
  const wrapper = mountWithVuetify(PluginResultsModal, {
    props: { modelValue: false, pluginName: 'ExamplePlugin', results },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('No Results Available')
  await wrapper.setProps({ error: 'Execution failed' })
  expect(dialog.text()).toContain('Execution failed')
})

it('explains a completed correlation scan with no matches', () => {
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: { result: [{ type: 'complete', data: {} }] },
  })
  expect(wrapper.get('[role="alert"]').text()).toBe(
    'Correlation scan complete. No correlations are available in accessible Cases.',
  )
})

it('does not describe a failed correlation scan as a successful empty result', () => {
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: {
      result: [
        { type: 'error', data: { message: 'Case not found' } },
        { type: 'complete', data: {} },
      ],
    },
  })
  expect(wrapper.get('[role="alert"]').text()).toBe('Case not found')
  expect(wrapper.text()).not.toContain('No correlations found')
  expect(wrapper.text()).not.toContain('Correlation scan complete')
})

it('offers optional saving for correlation without source or destination selectors', async () => {
  const { default: CorrelationScanPluginParams } = await import(
    '../plugins/CorrelationScanPluginParams.vue'
  )
  const wrapper = mountWithVuetify(CorrelationScanPluginParams, {
    props: { parameters: {}, modelValue: { save_to_case: false, case_id: 999 } },
  })
  await flushPromises()
  expect(wrapper.findAll('input')).toHaveLength(1)
  const toggle = wrapper.get('input[type="checkbox"]')
  expect(toggle.element.checked).toBe(false)
  await toggle.setValue(true)
  expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual({ save_to_case: true })
  expect(wrapper.text()).not.toContain('Case to Scan')
  expect(wrapper.text()).not.toContain('Case to Save')
})

it('renders retained typed events through the specialized correlation renderer', async () => {
  const { default: PluginResult } = await import('../plugins/PluginResult.vue')
  const wrapper = mountWithVuetify(PluginResult, {
    props: { pluginName: 'CorrelationScan', result: [{ type: 'complete', data: {} }] },
  })
  await vi.waitFor(() =>
    expect(wrapper.findComponent(CorrelationScanPluginResult).exists()).toBe(true),
  )
  expect(wrapper.text()).toContain('Correlation scan complete')
})

it('labels retained partial output and preserves its failure in exports', async () => {
  const wrapper = mountWithVuetify(PluginResultsModal, {
    props: {
      modelValue: false,
      pluginName: 'ExamplePlugin',
      results: [{ type: 'data', data: { match: 'example.org' } }],
      error: 'Output exceeds the operation limit',
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('Partial retained results')
  expect(dialog.text()).toContain('Output exceeds the operation limit')
  expect(dialog.text()).toContain('example.org')
  await dialog
    .findAll('button')
    .find((button) => button.text().includes('Export'))
    .trigger('click')
  expect(wrapper.emitted('export')[0][0]).toMatchObject({
    partial: true,
    error: 'Output exceeds the operation limit',
  })
})

it('renders field explanations and tentative vehicle qualifications', () => {
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: {
      result: [
        {
          type: 'data',
          data: {
            case_id: 1,
            entity_id: 10,
            entity_type: 'vehicle',
            entity_name: '',
            match_type: 'license_plate',
            normalized_value: 'OWL123',
            matched_value: 'OWL-123',
            source_fields: [{ field: 'license_plate', value: 'OWL-123' }],
            matches: [
              {
                case_id: 2,
                case_number: 'B',
                case_title: 'Related',
                entity_id: 20,
                entity_type: 'vehicle',
                entity_name: 'Blue van',
                fields: [{ field: 'license_plate', value: 'owl 123' }],
                signal:
                  'Tentative license plate association: registration state unknown; conflicting VINs',
              },
            ],
          },
        },
      ],
    },
  })
  for (const text of [
    'vehicle #10',
    'Blue van',
    'license_plate: OWL-123',
    'license_plate: owl 123',
    'registration state unknown',
    'conflicting VINs',
  ]) {
    expect(wrapper.text()).toContain(text)
  }
  expect(wrapper.text()).not.toContain('This indicates the same vehicle')
})

it('qualifies completed scans containing skipped references without rendering a match card', () => {
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: {
      result: [
        {
          type: 'data',
          data: {
            notice_type: 'skipped_reference',
            case_scope: [1],
            case_id: 1,
            entity_id: 10,
            field: 'usernames[0]',
            message: 'A malformed reference was skipped; reference coverage is incomplete.',
          },
        },
        { type: 'complete', data: {} },
      ],
    },
  })
  expect(wrapper.text()).toContain('reference coverage is incomplete')
  expect(wrapper.text()).toContain('completed with skipped references')
  expect(wrapper.text()).not.toContain('Found an entity')
})

it('keeps legacy related names and explanations readable with stable navigation', async () => {
  const push = vi.fn()
  vi.spyOn(await import('vue-router'), 'useRouter').mockReturnValue({ push })
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: {
      result: [
        {
          type: 'data',
          data: {
            case_id: 1,
            entity_id: 10,
            entity_type: 'person',
            entity_name: 'Ada',
            match_type: 'employer',
            employer_name: 'Engines',
            matches: [
              {
                case_id: 2,
                case_number: 'B',
                case_title: 'Related',
                entity_id: 20,
                entity_type: 'person',
                person_name: 'Charles',
                found_in: 'employer: Engines',
              },
            ],
          },
        },
      ],
    },
  })
  expect(wrapper.text()).toContain('Charles (person)')
  expect(wrapper.text()).toContain('employer: Engines')
  await wrapper.get('button').trigger('click')
  expect(push).toHaveBeenCalledWith({ path: '/case/2', query: { entity: 20 } })
})

it('assembles continued groups and ranks exact identifiers before provider overlap in cards and exports', async () => {
  const part = (kind, id, related, rank, signal) => ({
    type: 'data',
    data: {
      case_id: 1,
      entity_id: 10,
      entity_name: 'Ada',
      entity_type: 'person',
      group_id: id,
      continuation: 'merge',
      match_type: kind,
      normalized_value: kind,
      source_fields: [{ field: kind, value: 'Original source' }],
      matches: [
        {
          case_id: 2,
          entity_id: related,
          entity_name: `Related ${related}`,
          entity_type: 'person',
          fields: [{ field: kind, value: `Original ${related}` }],
          signal_rank: rank,
          signal,
        },
      ],
    },
  })
  const low = part('domain', 'domain-group', 21, 2, 'Low signal: common email provider')
  const email = part('email', 'email-group', 22, 0, 'Exact email match')
  const phone = part('phone', 'phone-group', 23, 0, 'Exact phone match')
  const continuation = part('email', 'email-group', 24, 0, 'Exact email match')
  const wrapper = mountWithVuetify(PluginResultsModal, {
    props: { modelValue: false, pluginName: 'CorrelationScan', results: [low, email, phone] },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  await wrapper.setProps({
    results: [low, email, phone, continuation, email, { type: 'complete', data: {} }],
  })
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  const cards = dialog.findAll('h3').map((heading) => heading.element.parentElement.textContent)
  expect(cards).toHaveLength(3)
  expect(cards[0]).toContain('Email Match')
  expect(cards[1]).toContain('Phone Match')
  expect(cards[2]).toContain('Domain Match')
  expect(dialog.text()).toContain('1 source Entities · 4 matches · 1 related Cases')
  expect(dialog.text()).toContain('Low signal: common email provider')
  expect(dialog.text()).toContain('Original 24')
  await dialog
    .findAll('button')
    .find((button) => button.text().includes('Export'))
    .trigger('click')
  const exported = wrapper.emitted('export')[0][0].results.filter((item) => item.data?.matches)
  expect(exported.map((item) => item.data.match_type)).toEqual(['email', 'phone', 'domain'])
  expect(exported[0].data.matches.map((match) => match.entity_id)).toEqual([22, 24])
  wrapper.unmount()
})

it('shows bounded progress while correlation output is still arriving', async () => {
  const progress = {
    type: 'status',
    data: { message: 'Indexed candidate Entities', count: 256, case_scope: [1, 2] },
  }
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, { props: { result: [progress] } })
  expect(wrapper.get('[role="status"]').text()).toContain('Indexed candidate Entities: 256')
  expect(wrapper.text()).not.toContain('No correlations are available')
  await wrapper.setProps({ result: [progress, { type: 'complete', data: {} }] })
  expect(wrapper.find('[role="status"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('Correlation scan complete')
})

it('presents and exports explicit IP connections with original fields alongside retained legacy reasons', async () => {
  const results = [
    {
      type: 'data',
      data: {
        case_id: 1,
        entity_id: 1,
        entity_type: 'ip_address',
        entity_name: '2001:db8::1',
        match_type: 'ip_address',
        normalized_value: '2001:db8::1',
        source_fields: [{ field: 'ip_address', value: '2001:db8::1' }],
        matches: [
          {
            case_id: 2,
            case_title: 'Related',
            case_number: 'IP-2',
            entity_id: 2,
            entity_type: 'ip_address',
            entity_name: '2001:0DB8:0:0:0:0:0:1',
            fields: [{ field: 'ip_address', value: '2001:0DB8:0:0:0:0:0:1' }],
            signal: 'Exact IP address match',
            signal_rank: 0,
          },
        ],
      },
    },
    {
      type: 'data',
      data: {
        case_id: 1,
        entity_id: 3,
        entity_type: 'ip_address',
        entity_name: '192.0.2.1',
        match_type: 'name',
        matches: [
          {
            case_id: 2,
            case_title: 'Legacy',
            case_number: 'OLD',
            entity_id: 4,
            entity_type: 'ip_address',
            entity_name: '192.0.2.1',
          },
        ],
      },
    },
  ]
  const wrapper = mountWithVuetify(PluginResultsModal, {
    props: { modelValue: false, pluginName: 'CorrelationScan', results },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('IP Address Match')
  expect(dialog.text()).toContain('Exact IP address match')
  expect(dialog.text()).toContain('2001:0DB8:0:0:0:0:0:1')
  expect(dialog.text()).toContain('Name Match')
  await dialog
    .findAll('button')
    .find((button) => button.text().includes('Export'))
    .trigger('click')
  const exported = wrapper.emitted('export')[0][0].results
  expect(exported).toHaveLength(2)
  expect(exported[0]).toEqual(results[0])
  expect(exported[1].data).toMatchObject(results[1].data)
  wrapper.unmount()
})

it('renders and exports recorded profile equality with every field and conservative qualification', async () => {
  const raw = ' HTTPS://EXAMPLE.COM./Ada?tag=One#Bio '
  const results = [
    {
      type: 'data',
      data: {
        case_id: 1,
        entity_id: 1,
        entity_type: 'person',
        entity_name: 'Ada',
        match_type: 'exact_profile',
        normalized_value: 'https://example.com/Ada?tag=One#Bio',
        source_fields: [
          { field: 'social_media.linkedin', value: raw },
          { field: 'usernames[0]', value: raw },
        ],
        matches: [
          {
            case_id: 2,
            case_title: 'Related',
            case_number: 'PROFILE-2',
            entity_id: 2,
            entity_type: 'company',
            entity_name: 'Engines',
            fields: [{ field: 'social_media.other', value: 'https://example.com/Ada?tag=One#Bio' }],
            signal:
              'Equal recorded profile reference; personal identity and account ownership are not established',
          },
        ],
      },
    },
  ]
  const wrapper = mountWithVuetify(PluginResultsModal, {
    props: { modelValue: false, pluginName: 'CorrelationScan', results },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.text()).toContain('Exact Profile Reference')
  expect(dialog.text()).toContain('personal identity and account ownership are not established')
  for (const field of ['social_media.linkedin', 'usernames[0]', 'social_media.other'])
    expect(dialog.text()).toContain(field)
  expect(dialog.text()).toContain(raw.trim())
  await dialog
    .findAll('button')
    .find((button) => button.text().includes('Export'))
    .trigger('click')
  expect(wrapper.emitted('export')[0][0].results).toEqual(results)
  wrapper.unmount()
})

it('qualifies retained counts until retrieval finishes despite a completed event', async () => {
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: {
      result: [{ type: 'complete', data: {} }],
      executionStatus: 'completed',
      retrievalComplete: false,
    },
  })
  expect(wrapper.text()).not.toContain('Correlation scan complete')
  expect(wrapper.text()).toContain('Partial retained results')
  await wrapper.setProps({ retrievalComplete: true })
  expect(wrapper.text()).toContain('No correlations are available')
  await wrapper.setProps({ executionStatus: 'cancelled' })
  expect(wrapper.text()).not.toContain('Correlation scan complete')
  expect(wrapper.text()).toContain('cancelled')
})

it('collapses readable weak matches in mixed groups and preserves expansion through continuation', async () => {
  const group = (matches) => ({
    type: 'data',
    data: {
      case_id: 1,
      entity_id: 10,
      entity_name: 'Mailbox owner',
      entity_type: 'person',
      group_id: 'mixed',
      match_type: 'domain',
      normalized_value: 'gmail.com',
      source_fields: [{ field: 'email', value: 'ada@gmail.com' }],
      matches,
    },
  })
  const ordinary = { case_id: 2, entity_id: 20, entity_name: 'Explicit Domain', signal_rank: 1 }
  const weak = (id) => ({
    case_id: 2,
    entity_id: id,
    entity_name: `Mailbox ${id}`,
    signal_rank: 2,
    signal: 'Low signal: common email provider',
  })
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: { result: [group([ordinary, weak(21), weak(22)])] },
  })
  expect(wrapper.get('details').element.open).toBe(false)
  expect(wrapper.get('summary').text()).toBe('Weak provider matches (2)')
  expect(wrapper.get('details').text()).not.toContain('Explicit Domain')
  wrapper.get('details').element.open = true
  await wrapper.setProps({
    result: [group([ordinary, weak(21), weak(22)]), group([weak(22), weak(23)])],
  })
  expect(wrapper.get('details').element.open).toBe(true)
  expect(wrapper.get('summary').text()).toBe('Weak provider matches (3)')
  expect(wrapper.findAll('h4')).toHaveLength(4)
  expect(wrapper.text()).toContain('Source email: ada@gmail.com')
})

it('shows the latest progress once without repeated status keys and hides it at durable termination', async () => {
  const warn = vi.spyOn(console, 'warn')
  const status = (count) => ({ type: 'status', data: { message: 'Indexed Entities', count } })
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: { result: [status(1), status(2), status(3)], executionStatus: 'running' },
  })
  expect(wrapper.findAll('[role="status"]')).toHaveLength(1)
  expect(wrapper.text()).toContain('Indexed Entities: 3')
  expect(wrapper.text()).not.toContain('Indexed Entities: 1')
  await wrapper.setProps({ executionStatus: 'failed' })
  expect(wrapper.find('[role="status"]').exists()).toBe(false)
  expect(warn.mock.calls.flat().join(' ')).not.toContain('Duplicate keys')
  warn.mockRestore()
})

it('places legacy weak-only groups after useful associations', () => {
  const group = (id, kind, signal) => ({
    type: 'data',
    data: {
      case_id: 1,
      entity_id: id,
      entity_name: `Source ${id}`,
      match_type: kind,
      matches: [{ case_id: 2, entity_id: id + 10, signal }],
    },
  })
  const wrapper = mountWithVuetify(CorrelationScanPluginResult, {
    props: {
      result: [
        group(1, 'domain', 'Low signal: common email provider'),
        group(2, 'employer', 'Shared employer'),
      ],
    },
  })
  expect(wrapper.findAll('h3').map((h) => h.text())).toEqual(['Source 2', 'Source 1'])
})
