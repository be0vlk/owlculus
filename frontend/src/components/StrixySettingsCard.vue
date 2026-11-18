<template>
  <v-card :elevation="0" class="strixy-workspace" variant="flat">
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <div>
        <h2 class="text-title-large font-weight-bold">Strixy</h2>
        <div class="text-body-medium text-medium-emphasis">
          Choose the provider and model Strixy uses for new runs
        </div>
      </div>
    </v-card-title>

    <v-divider />

    <v-card-text class="pa-4">
      <v-progress-linear v-if="loading" indeterminate aria-label="Loading Strixy settings" />
      <v-alert v-if="loadError" type="error" variant="tonal" class="mb-4">
        {{ loadError }}
        <v-btn variant="text" @click="load">Retry</v-btn>
      </v-alert>
      <v-container v-else fluid class="pa-0">
        <v-row>
          <v-col cols="12" lg="6">
            <v-select
              :model-value="form.provider"
              :disabled="loading"
              :items="providerItems"
              label="Provider"
              prepend-inner-icon="mdi-cloud-outline"
              @update:model-value="changeProvider"
            />
          </v-col>
          <v-col cols="12" lg="6">
            <v-text-field
              v-model="apiKey"
              :disabled="loading"
              :placeholder="keyConfigured ? 'Saved, leave blank to keep' : undefined"
              :hint="keyHint"
              :persistent-hint="!keyConfigured"
              autocomplete="off"
              label="API key"
              prepend-inner-icon="mdi-key-outline"
              type="password"
              @blur="typedKey() && loadModels()"
            />
          </v-col>
          <v-col v-if="isCompatible" cols="12">
            <v-text-field
              v-model="form.base_url"
              :disabled="loading"
              :rules="[validateUrl]"
              label="Base URL"
              placeholder="http://host:port/v1"
              prepend-inner-icon="mdi-link-variant"
              @blur="loadModels"
            />
          </v-col>
          <v-col cols="12" lg="6">
            <v-combobox
              :model-value="form.model"
              :disabled="loading"
              :items="modelItems"
              :loading="modelsLoading"
              :error-messages="modelsError"
              :label="needsModel ? 'Model' : 'Model (optional)'"
              :placeholder="defaultModel"
              :rules="needsModel ? [required('Model')] : []"
              :hint="needsModel ? undefined : `Leave blank to use ${defaultModel}`"
              :persistent-hint="!needsModel"
              :return-object="false"
              append-icon="mdi-refresh"
              prepend-inner-icon="mdi-chip"
              @click:append="loadModels"
              @update:model-value="setModel"
            />
          </v-col>
          <v-col v-if="!isCompatible" cols="12" lg="6">
            <v-select
              v-model="form.reasoning_effort"
              :disabled="loading || noEffort"
              :items="effortItems"
              :hint="noEffort ? 'This model does not take a reasoning effort' : undefined"
              :persistent-hint="noEffort"
              label="Reasoning effort"
              prepend-inner-icon="mdi-brain"
            />
          </v-col>
          <v-col cols="12">
            <v-switch
              v-model="form.supports_vision"
              :disabled="loading"
              label="Model accepts images"
              color="primary"
              hide-details
            />
          </v-col>
          <v-col v-if="testResult" cols="12">
            <v-alert :type="testResult.ok ? 'success' : 'error'" variant="tonal">
              {{ testResult.text }}
            </v-alert>
          </v-col>
        </v-row>
      </v-container>
    </v-card-text>

    <v-divider />

    <v-card-actions class="pa-4 flex-wrap">
      <v-spacer />
      <v-btn
        variant="tonal"
        prepend-icon="mdi-connection"
        :loading="testing"
        :disabled="loading || !!loadError || !isValid"
        @click="testConnection"
      >
        Test connection
      </v-btn>
      <v-btn
        variant="text"
        prepend-icon="mdi-refresh"
        :disabled="loading || !!loadError || !isChanged"
        @click="reset"
      >
        Reset
      </v-btn>
      <v-btn
        color="primary"
        prepend-icon="mdi-content-save"
        :loading="loading"
        :disabled="!isChanged || !isValid || loading || !!loadError"
        @click="save"
      >
        Save Settings
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import api from '@/services/api'

const emit = defineEmits(['notification'])

const base = '/api/admin/configuration/strixy'
const efforts = ['low', 'medium', 'high', 'xhigh', 'max']
const blank = () => ({
  provider: 'openai',
  model: '',
  base_url: '',
  supports_vision: true,
  reasoning_effort: 'low',
})

const form = reactive(blank())
const apiKey = ref('')
const saved = ref(null)
const providers = ref({})
const loading = ref(false)
const loadError = ref('')
const models = ref([])
const modelsLoading = ref(false)
const modelsError = ref('')
const testing = ref(false)
const testResult = ref(null)
let modelsRequest = 0

const isCompatible = computed(() => form.provider === 'openai_compatible')
const defaultModel = computed(() => providers.value[form.provider]?.default_model || '')
const needsModel = computed(() => !defaultModel.value)
const keyConfigured = computed(() => !!providers.value[form.provider]?.key_configured)
const keyHint = computed(() => {
  if (keyConfigured.value) return undefined
  return isCompatible.value ? 'Optional' : 'Needed for Strixy to run'
})
const providerItems = computed(() =>
  Object.entries(providers.value).map(([value, { name }]) => ({ value, title: name })),
)
const modelItems = computed(() => models.value.map((m) => ({ title: m.name, value: m.id })))
const selectedModel = computed(() => models.value.find((m) => m.id === form.model))
const noEffort = computed(() => selectedModel.value?.efforts?.length === 0)
const effortItems = computed(() => [
  { title: 'Model default', value: null },
  ...(selectedModel.value?.efforts || efforts).map((value) => ({ title: value, value })),
])

const required = (label) => (v) => !!v?.trim() || `${label} is required`
const validateUrl = (v) =>
  /^https?:\/\/\S+$/.test(v?.trim() || '') || 'Enter an http:// or https:// URL'

const payload = () => ({
  provider: form.provider,
  model: form.model?.trim() || null,
  base_url: isCompatible.value ? form.base_url?.trim() || null : null,
  supports_vision: form.supports_vision,
  reasoning_effort: form.reasoning_effort,
})
const typedKey = () => apiKey.value.trim()
const withKey = () => (typedKey() ? { ...payload(), api_key: typedKey() } : payload())

const isChanged = computed(
  () => !!typedKey() || JSON.stringify(payload()) !== JSON.stringify(saved.value),
)
const isValid = computed(
  () =>
    (!needsModel.value || required('Model')(form.model) === true) &&
    (!isCompatible.value || validateUrl(form.base_url) === true),
)

watch([() => JSON.stringify(payload()), apiKey], () => {
  testResult.value = null
})

const apply = (data) => {
  providers.value = data.providers
  Object.assign(form, {
    provider: data.provider,
    model: data.model ?? '',
    base_url: data.base_url ?? '',
    supports_vision: data.supports_vision,
    reasoning_effort: data.reasoning_effort,
  })
  saved.value = payload()
}

const resetModels = () => {
  models.value = []
  modelsError.value = ''
  loadModels()
}

const reset = () => {
  const providerChanged = form.provider !== saved.value.provider
  apply({ ...saved.value, providers: providers.value })
  apiKey.value = ''
  if (providerChanged) resetModels()
}

const errorText = (error, fallback) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
  return fallback
}

const loadModels = async () => {
  const canList =
    typedKey() || keyConfigured.value || (isCompatible.value && validateUrl(form.base_url) === true)
  if (!canList) return
  const request = ++modelsRequest
  modelsLoading.value = true
  modelsError.value = ''
  try {
    const body = { provider: form.provider }
    if (isCompatible.value) body.base_url = form.base_url.trim()
    if (typedKey()) body.api_key = typedKey()
    const { data } = await api.post(`${base}/models`, body)
    if (request === modelsRequest) models.value = data.models
  } catch (error) {
    if (request === modelsRequest) {
      modelsError.value = errorText(error, 'Could not load the model list.')
    }
  } finally {
    if (request === modelsRequest) modelsLoading.value = false
  }
}

const changeProvider = (provider) => {
  form.provider = provider
  form.model = provider === saved.value?.provider ? (saved.value.model ?? '') : ''
  apiKey.value = ''
  resetModels()
}

const setModel = (value) => {
  form.model = value ?? ''
  const model = selectedModel.value
  if (!model) return
  if (model.vision !== null) form.supports_vision = model.vision
  if (!model.efforts) return
  if (!model.efforts.length) form.reasoning_effort = null
  else if (form.reasoning_effort && !model.efforts.includes(form.reasoning_effort)) {
    form.reasoning_effort = model.efforts[0]
  }
}

const load = async () => {
  loadError.value = ''
  loading.value = true
  try {
    apply((await api.get(base)).data)
  } catch {
    loadError.value = 'Failed to load Strixy settings. Please try again.'
    return
  } finally {
    loading.value = false
  }
  loadModels()
}

const testConnection = async () => {
  testing.value = true
  testResult.value = null
  try {
    const { data } = await api.post(`${base}/test`, withKey())
    testResult.value = data.ok
      ? {
          ok: true,
          text: `Connected: ${data.model} answered in ${Math.round(data.seconds * 10) / 10}s`,
        }
      : { ok: false, text: data.message }
  } catch (error) {
    testResult.value = { ok: false, text: errorText(error, 'Connection test failed.') }
  } finally {
    testing.value = false
  }
}

const save = async () => {
  loading.value = true
  try {
    apply((await api.put(base, withKey())).data)
    apiKey.value = ''
    emit('notification', { text: 'Strixy settings saved successfully!', color: 'success' })
  } catch (error) {
    console.error('Error saving Strixy settings:', error)
    emit('notification', {
      text: errorText(error, 'Failed to save Strixy settings. Please try again.'),
      color: 'error',
    })
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.strixy-workspace {
  max-width: 900px;
}
</style>
