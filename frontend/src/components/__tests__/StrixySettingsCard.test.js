import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithVuetify } from './helpers/vuetify'
import StrixySettingsCard from '../StrixySettingsCard.vue'
import api from '@/services/api'

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))

const providers = {
  openai: { name: 'OpenAI', default_model: 'gpt-6-astra', key_configured: false },
  openai_compatible: { name: 'OpenAI-compatible', default_model: '', key_configured: false },
  anthropic: { name: 'Anthropic', default_model: 'claude-opus-9', key_configured: false },
  openrouter: { name: 'OpenRouter', default_model: '', key_configured: false },
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
const combo = (wrapper) => wrapper.findComponent({ name: 'VCombobox' })
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
    expect(combo(wrapper).props('modelValue')).toBe('claude-custom')
    expect(combo(wrapper).props('placeholder')).toBe('claude-opus-9')
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

    await combo(wrapper).vm.$emit('update:modelValue', 'llama')
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
    await combo(wrapper).vm.$emit('update:modelValue', '  ')
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
    expect(api.put.mock.calls[0][1]).not.toHaveProperty('api_key')
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

  describe('guided setup', () => {
    const modelsUrl = '/api/admin/configuration/strixy/models'
    const models = [
      { id: 'a/vision', name: 'Vision', vision: true, efforts: null },
      { id: 'b/plain', name: 'Plain', vision: false, efforts: [] },
      { id: 'c/some', name: 'Some', vision: null, efforts: ['low', 'high'] },
    ]
    const keyed = {
      ...settings,
      provider: 'openrouter',
      model: 'a/vision',
      providers: { ...providers, openrouter: { ...providers.openrouter, key_configured: true } },
    }

    it('loads the model list into the combobox when a key is saved', async () => {
      api.post.mockResolvedValue({ data: { models } })
      const wrapper = await mountCard(keyed)
      expect(api.post).toHaveBeenCalledWith(modelsUrl, { provider: 'openrouter' })
      expect(combo(wrapper).props('items')).toEqual([
        { title: 'Vision', value: 'a/vision' },
        { title: 'Plain', value: 'b/plain' },
        { title: 'Some', value: 'c/some' },
      ])
    })

    it('does not list models without a key, then lists after a typed key', async () => {
      api.post.mockResolvedValue({ data: { models } })
      const wrapper = await mountCard({ ...settings, provider: 'openrouter' })
      expect(api.post).not.toHaveBeenCalled()
      expect(field(wrapper, 'API key').props('hint')).toBe('Needed for Strixy to run')

      await field(wrapper, 'API key').vm.$emit('update:modelValue', 'sk-new')
      await field(wrapper, 'API key').find('input').trigger('blur')
      await flushPromises()
      expect(api.post).toHaveBeenCalledWith(modelsUrl, { provider: 'openrouter', api_key: 'sk-new' })
    })

    it('shows a list error without blocking Save', async () => {
      api.post.mockRejectedValue({ response: { data: { detail: 'Key rejected' } } })
      const wrapper = await mountCard(keyed)
      expect(wrapper.text()).toContain('Key rejected')
      await combo(wrapper).vm.$emit('update:modelValue', 'typed/model')
      await flushPromises()
      expect(button(wrapper, 'Save Settings').attributes('disabled')).toBeUndefined()
    })

    it('adopts vision and effort from a picked model', async () => {
      api.post.mockResolvedValue({ data: { models } })
      const wrapper = await mountCard(keyed)

      await combo(wrapper).vm.$emit('update:modelValue', 'b/plain')
      await flushPromises()
      expect(wrapper.get('input[type="checkbox"]').element.checked).toBe(false)
      expect(select(wrapper, 'Reasoning effort').props('modelValue')).toBe(null)
      expect(select(wrapper, 'Reasoning effort').props('disabled')).toBe(true)

      await combo(wrapper).vm.$emit('update:modelValue', 'c/some')
      await flushPromises()
      expect(wrapper.get('input[type="checkbox"]').element.checked).toBe(false)
      expect(select(wrapper, 'Reasoning effort').props('items').map((i) => i.value)).toEqual([
        null,
        'low',
        'high',
      ])
    })

    it('sends a typed key in the PUT and clears it afterwards', async () => {
      const wrapper = await mountCard({ ...settings, provider: 'openrouter' })
      await field(wrapper, 'API key').vm.$emit('update:modelValue', ' sk-new ')
      await combo(wrapper).vm.$emit('update:modelValue', 'x/y')
      await flushPromises()
      api.put.mockResolvedValue({ data: { ...settings, provider: 'openrouter', model: 'x/y' } })
      await button(wrapper, 'Save Settings').trigger('click')
      await flushPromises()
      expect(api.put).toHaveBeenCalledWith('/api/admin/configuration/strixy', {
        provider: 'openrouter',
        model: 'x/y',
        base_url: null,
        supports_vision: true,
        reasoning_effort: 'low',
        api_key: 'sk-new',
      })
      expect(field(wrapper, 'API key').props('modelValue')).toBe('')
    })

    it('tests the connection with the current form and shows the outcome', async () => {
      api.post.mockResolvedValueOnce({ data: { models } })
      const wrapper = await mountCard(keyed)
      api.post.mockResolvedValueOnce({ data: { ok: true, model: 'a/vision', seconds: 2.3 } })
      await button(wrapper, 'Test connection').trigger('click')
      await flushPromises()
      expect(api.post).toHaveBeenLastCalledWith('/api/admin/configuration/strixy/test', {
        provider: 'openrouter',
        model: 'a/vision',
        base_url: null,
        supports_vision: true,
        reasoning_effort: 'low',
      })
      expect(wrapper.text()).toContain('Connected: a/vision answered in 2.3s')

      await select(wrapper, 'Reasoning effort').vm.$emit('update:modelValue', 'high')
      await flushPromises()
      expect(wrapper.text()).not.toContain('Connected:')

      api.post.mockResolvedValueOnce({ data: { ok: false, message: 'No endpoints found' } })
      await button(wrapper, 'Test connection').trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('No endpoints found')
    })

    it('disables Test connection while the form is invalid', async () => {
      const wrapper = await mountCard({ ...settings, provider: 'openrouter' })
      expect(button(wrapper, 'Test connection').attributes('disabled')).toBeDefined()
    })
  })
})
