import { expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import HuntParameterForm from '../hunts/HuntParameterForm.vue'

it('accepts zero, preserves defaults, and renders multiline and server errors accessibly', async () => {
  const wrapper = mountWithVuetify(HuntParameterForm, {
    props: {
      parameters: {
        limit: { type: 'number', required: true, min: 0, default: 0 },
        notes: { type: 'string', multiline: true, default: 'Investigation notes' },
      },
      modelValue: {},
    },
  })
  await flushPromises()
  expect(await wrapper.vm.validate()).toBe(true)
  expect(wrapper.get('textarea').element.value).toBe('Investigation notes')
  await wrapper.setProps({ errors: { limit: 'Limit unavailable' } })
  await flushPromises()
  expect(wrapper.text()).toContain('Limit unavailable')
  expect(wrapper.get('input[type="number"]').attributes('aria-invalid')).toBe('true')
})

it('validates before execution, submits defaults, and retains failure feedback while open', async () => {
  const { default: HuntExecutionModal } = await import('../hunts/HuntExecutionModal.vue')
  const { DOMWrapper } = await import('@vue/test-utils')
  const wrapper = mountWithVuetify(HuntExecutionModal, {
    props: {
      modelValue: false,
      caseId: 4,
      hunt: {
        id: 7,
        display_name: 'Domain Hunt',
        initial_parameters: {
          domain: { type: 'string', required: true },
          limit: { type: 'number', default: 0 },
        },
      },
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('execute')).toBeUndefined()
  expect(dialog.text()).toContain('Domain is required')
  await dialog.get('input[type="text"]').setValue('example.org')
  await dialog.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('execute')).toEqual([
    [{ huntId: 7, caseId: 4, parameters: { domain: 'example.org', limit: 0 } }],
  ])
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  await wrapper.setProps({ executing: true })
  expect(dialog.get('button[aria-label="Close hunt configuration"]').element.disabled).toBe(true)
  await wrapper.setProps({ executing: false, error: 'Execution unavailable' })
  expect(
    dialog
      .findAll('[role="alert"]')
      .some((alert) => alert.text().includes('Execution unavailable')),
  ).toBe(true)
  expect(dialog.get('input[type="text"]').element.value).toBe('example.org')
})

it('has no case selector and blocks execution without resolved context', async () => {
  const { default: HuntExecutionModal } = await import('../hunts/HuntExecutionModal.vue')
  const { DOMWrapper } = await import('@vue/test-utils')
  const wrapper = mountWithVuetify(HuntExecutionModal, {
    props: { modelValue: false, hunt: { id: 7 } },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const dialog = new DOMWrapper(document.querySelector('[role="dialog"]'))
  expect(dialog.find('input[role="combobox"]').exists()).toBe(false)
  expect(dialog.get('button[type="submit"]').element.disabled).toBe(true)
  await dialog.get('form').trigger('submit')
  expect(wrapper.emitted('execute')).toBeUndefined()
})

it.each(['failed', 'running', 'cancelled'])(
  'shows useful partial results from a %s hunt step',
  async (status) => {
    const { default: HuntStepResults } = await import('../hunts/HuntStepResults.vue')
    const wrapper = mountWithVuetify(HuntStepResults, {
      props: {
        stepNumber: 1,
        step: {
          step_id: 'lookup',
          plugin_name: 'Lookup',
          status,
          output: { results: [{ finding: 'Retained finding' }], errors: [], result_count: 1 },
        },
      },
    })
    expect(wrapper.text()).toContain('Partial retained results')
    expect(wrapper.text()).toContain('Retained finding')
  },
)

it('shows a skipped Entity save explanation in a completed Hunt step', async () => {
  const { default: HuntStepResults } = await import('../hunts/HuntStepResults.vue')
  const wrapper = mountWithVuetify(HuntStepResults, {
    props: {
      stepNumber: 2,
      step: {
        step_id: 'lookup',
        plugin_name: 'DnsLookup',
        status: 'completed',
        output: {
          results: [
            {
              notice_type: 'entity_save_skipped',
              message:
                'Entity save skipped: correlation provenance does not permit saving to this Case.',
            },
          ],
          errors: [],
          result_count: 1,
        },
      },
    },
  })
  expect(wrapper.text()).toContain(
    'Entity save skipped: correlation provenance does not permit saving to this Case.',
  )
  expect(wrapper.text()).not.toContain('This step has not completed successfully')
})

it('assembles Hunt correlation portions like standalone results and retains navigation and expansion', async () => {
  const { default: HuntStepResults } = await import('../hunts/HuntStepResults.vue')
  const { default: CorrelationScanPluginResult } = await import(
    '../plugins/CorrelationScanPluginResult.vue'
  )
  const { createRouter, createMemoryHistory } = await import('vue-router')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  const part = (matches) => ({
    case_id: 1,
    entity_id: 10,
    entity_type: 'person',
    match_type: 'domain',
    normalized_value: 'gmail.com',
    source_fields: [{ field: 'email', value: 'ada@gmail.com' }],
    matches,
  })
  const ordinary = {
    case_id: 2,
    case_number: 'OTHER',
    entity_id: 20,
    entity_name: 'Explicit Domain',
    signal_rank: 1,
    fields: [{ field: 'domain', value: 'gmail.com' }],
  }
  const weak = { case_id: 2, entity_id: 21, entity_name: 'Mailbox', signal_rank: 2 }
  const results = [part([ordinary, weak]), part([ordinary])]
  const step = {
    step_id: 'scan',
    plugin_name: 'CorrelationScan',
    status: 'running',
    output: { results, errors: [], partial: true },
  }
  const wrapper = mountWithVuetify(HuntStepResults, {
    props: { step, stepNumber: 1 },
    global: { plugins: [router] },
  })
  await flushPromises()
  expect(wrapper.text()).toContain('1 source Entities · 2 matches · 1 related Cases')
  expect(wrapper.text()).toContain('person #10')
  expect(wrapper.text()).toContain('Source email: ada@gmail.com')
  expect(wrapper.text()).toContain('Related domain: gmail.com')
  expect(wrapper.text()).toContain('Execution running')
  const standalone = mountWithVuetify(CorrelationScanPluginResult, {
    props: {
      result: results.map((data) => ({ type: 'data', data })),
      executionStatus: 'running',
      executionPartial: true,
    },
    global: { plugins: [router] },
  })
  expect(wrapper.getComponent(CorrelationScanPluginResult).text()).toBe(standalone.text())
  expect(wrapper.get('details').element.open).toBe(false)
  wrapper.get('details').element.open = true
  await wrapper.setProps({
    step: {
      ...step,
      output: { ...step.output, results: [...results, part([{ ...weak, entity_id: 22 }])] },
    },
  })
  await flushPromises()
  expect(wrapper.get('details').element.open).toBe(true)
  expect(wrapper.get('summary').text()).toBe('Weak provider matches (2)')
  await wrapper
    .findAll('button')
    .find((button) => button.text().includes('View Entity'))
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query).toEqual({ entity: '20' })
})

it.each(['pending', 'running', 'failed', 'cancelled', 'skipped', 'completed'])(
  'keeps %s correlation state separate from retrieval and partial output',
  async (status) => {
    const { default: HuntStepResults } = await import('../hunts/HuntStepResults.vue')
    const wrapper = mountWithVuetify(HuntStepResults, {
      props: {
        stepNumber: 1,
        step: {
          step_id: 'scan',
          plugin_name: 'CorrelationScan',
          status,
          output: { results: [], errors: [] },
        },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain(`Step ${status}`)
    expect(wrapper.text().includes('No correlations are available')).toBe(status === 'completed')
    await wrapper.setProps({
      retrievalLoading: true,
      retrievalComplete: false,
      retrievalError: 'Retained read unavailable',
    })
    expect(wrapper.text()).toContain('Loading retained results')
    expect(wrapper.text()).toContain('Retained read unavailable')
    expect(wrapper.text()).not.toContain('No correlations are available')
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('Retry retrieval'))
      .trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    await wrapper.setProps({
      retrievalLoading: false,
      retrievalComplete: true,
      retrievalError: null,
      step: { ...wrapper.props('step'), output: { results: [], partial: true, errors: [] } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Partial retained output')
    expect(wrapper.text()).not.toContain('counts reflect loaded matches')
    expect(wrapper.text()).not.toContain('No correlations are available')
  },
)

it.each(['ip_address', 'exact_profile', 'employer', 'name'])(
  'presents legacy and new %s Hunt groups, skipped references, and retained errors',
  async (kind) => {
    const { default: HuntStepResults } = await import('../hunts/HuntStepResults.vue')
    const { default: CorrelationScanPluginResult } = await import(
      '../plugins/CorrelationScanPluginResult.vue'
    )
    const results = [
      {
        case_id: 1,
        entity_id: 10,
        entity_type: 'person',
        match_type: kind,
        matches: [{ case_id: 2, entity_id: 20, found_in: 'Legacy field explanation' }],
      },
      {
        notice_type: 'skipped_reference',
        message: 'Reference coverage is incomplete.',
        field: 'email',
      },
    ]
    const error = {
      message: 'Correlation scan could not complete. Available results may be partial.',
    }
    const step = {
      step_id: 'scan',
      plugin_name: 'CorrelationScan',
      status: 'failed',
      output: { results, errors: [error], partial: true },
    }
    const wrapper = mountWithVuetify(HuntStepResults, { props: { step, stepNumber: 1 } })
    await flushPromises()
    const standalone = mountWithVuetify(CorrelationScanPluginResult, {
      props: {
        result: [
          ...results.map((data) => ({ type: 'data', data })),
          { type: 'error', data: error },
        ],
        executionStatus: 'failed',
        executionPartial: true,
      },
    })
    expect(wrapper.getComponent(CorrelationScanPluginResult).text()).toBe(standalone.text())
    expect(wrapper.text()).toContain('1 source Entities · 1 matches · 1 related Cases')
    expect(wrapper.text()).toContain('Legacy field explanation')
    expect(wrapper.text()).toContain('Reference coverage is incomplete')
    expect(wrapper.text()).toContain(error.message)
    expect(wrapper.text()).not.toContain('Correlation scan complete')
  },
)

it('counts assembled correlation groups in Hunt summaries and progress', async () => {
  const { default: HuntResultsSummary } = await import('../hunts/HuntResultsSummary.vue')
  const { default: HuntStepProgress } = await import('../hunts/HuntStepProgress.vue')
  const group = {
    case_id: 1,
    entity_id: 10,
    match_type: 'email',
    matches: [{ case_id: 2, entity_id: 20 }],
  }
  const step = {
    step_id: 'scan',
    plugin_name: 'CorrelationScan',
    status: 'completed',
    output: {
      results: [group, group, { notice_type: 'skipped_reference', message: 'Skipped' }],
      result_count: 3,
    },
  }
  const summary = mountWithVuetify(HuntResultsSummary, { props: { execution: { steps: [step] } } })
  expect(summary.text()).toContain('1Total Results')
  const progress = mountWithVuetify(HuntStepProgress, { props: { step, stepNumber: 1 } })
  expect(progress.text()).toContain('1 correlation group(s)')
})

it('announces a correlation failure once when step and retained errors agree', async () => {
  const { default: HuntStepResults } = await import('../hunts/HuntStepResults.vue')
  const message = 'Correlation scan could not complete.'
  const step = {
    step_id: 'scan',
    plugin_name: 'CorrelationScan',
    status: 'failed',
    error_details: message,
    output: { results: [], errors: [] },
  }
  const wrapper = mountWithVuetify(HuntStepResults, { props: { step, stepNumber: 1 } })
  await flushPromises()
  expect(wrapper.text().split(message)).toHaveLength(2)
  await wrapper.setProps({ step: { ...step, output: { results: [], errors: [{ message }] } } })
  await flushPromises()
  expect(wrapper.text().split(message)).toHaveLength(2)
})
