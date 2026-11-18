import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import StrixySettingsCard from '../StrixySettingsCard.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), put: vi.fn() } }))

const providers = {
  openai: { name: 'OpenAI', default_model: 'gpt-6-astra' },
  openai_compatible: { name: 'OpenAI-compatible', default_model: '' },
  anthropic: { name: 'Anthropic', default_model: 'claude-opus-9' },
}
const settings = {
  provider: 'openai',
  model: null,
  base_url: null,
  supports_vision: true,
  reasoning_effort: 'low',
  providers,
}

const field = (wrapper, label) =>
  wrapper.findAllComponents({ name: 'VTextField' }).find((c) => c.props('label') === label)
const select = (wrapper, label) =>
  wrapper.findAllComponents({ name: 'VSelect' }).find((c) => c.props('label') === label)
const button = (wrapper, text) => wrapper.findAll('button').find((b) => b.text() === text)

async function mountCard(data = settings) {
  api.get.mockResolvedValue({ data })
  const wrapper = mountWithVuetify(StrixySettingsCard)
  await flushPromises()
  return wrapper
}

describe('StrixySettingsCard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('populates the fields from the loaded settings', async () => {
    const wrapper = await mountCard({
      ...settings,
      provider: 'anthropic',
      model: 'claude-custom',
      reasoning_effort: 'high',
      supports_vision: false,
    })
    expect(api.get).toHaveBeenCalledWith('/api/admin/configuration/strixy')
    expect(select(wrapper, 'Provider').props('modelValue')).toBe('anthropic')
    expect(field(wrapper, 'Model (optional)').props('modelValue')).toBe('claude-custom')
    expect(field(wrapper, 'Model (optional)').props('placeholder')).toBe('claude-opus-9')
    expect(select(wrapper, 'Reasoning effort').props('modelValue')).toBe('high')
    expect(wrapper.get('input[type="checkbox"]').element.checked).toBe(false)
    expect(wrapper.text()).toContain('Model accepts images')
    expect(field(wrapper, 'Base URL')).toBeUndefined()
    expect(button(wrapper, 'Save Settings').attributes('disabled')).toBeDefined()
  })

  it('requires model and base URL for OpenAI-compatible before Save', async () => {
    const wrapper = await mountCard()
    await select(wrapper, 'Provider').vm.$emit('update:modelValue', 'openai_compatible')
    await flushPromises()

    expect(field(wrapper, 'Base URL')).toBeDefined()
    expect(select(wrapper, 'Reasoning effort')).toBeUndefined()
    expect(button(wrapper, 'Save Settings').attributes('disabled')).toBeDefined()

    await field(wrapper, 'Model').vm.$emit('update:modelValue', 'llama')
    await field(wrapper, 'Base URL').vm.$emit('update:modelValue', 'ftp://host')
    await flushPromises()
    expect(button(wrapper, 'Save Settings').attributes('disabled')).toBeDefined()

    await field(wrapper, 'Base URL').vm.$emit('update:modelValue', 'http://host:8000/v1')
    await flushPromises()
    expect(button(wrapper, 'Save Settings').attributes('disabled')).toBeUndefined()
  })

  it('PUTs the right body and shows backend errors', async () => {
    const wrapper = await mountCard({ ...settings, model: 'old', base_url: 'http://stale' })
    await select(wrapper, 'Provider').vm.$emit('update:modelValue', 'anthropic')
    await field(wrapper, 'Model (optional)').vm.$emit('update:modelValue', '  ')
    await select(wrapper, 'Reasoning effort').vm.$emit('update:modelValue', 'max')
    await flushPromises()

    api.put.mockResolvedValue({
      data: {
        ...settings,
        provider: 'anthropic',
        reasoning_effort: 'max',
      },
    })
    await button(wrapper, 'Save Settings').trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/api/admin/configuration/strixy', {
      provider: 'anthropic',
      model: null,
      base_url: null,
      supports_vision: true,
      reasoning_effort: 'max',
    })
    expect(wrapper.emitted('notification').at(-1)[0].color).toBe('success')

    await select(wrapper, 'Reasoning effort').vm.$emit('update:modelValue', 'low')
    await flushPromises()
    api.put.mockRejectedValue({ response: { data: { detail: [{ msg: 'bad effort' }] } } })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await button(wrapper, 'Save Settings').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('notification').at(-1)[0]).toEqual({
      text: 'bad effort',
      color: 'error',
    })
  })

  it('shows a retry alert when loading fails', async () => {
    api.get.mockRejectedValueOnce(new Error('boom'))
    const wrapper = mountWithVuetify(StrixySettingsCard)
    await flushPromises()
    expect(wrapper.text()).toContain('Failed to load Strixy settings')
    api.get.mockResolvedValue({ data: settings })
    await button(wrapper, 'Retry').trigger('click')
    await flushPromises()
    expect(select(wrapper, 'Provider').props('modelValue')).toBe('openai')
  })
})
