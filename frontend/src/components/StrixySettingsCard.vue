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
              v-model="form.provider"
              :disabled="loading"
              :items="providerItems"
              label="Provider"
              prepend-inner-icon="mdi-cloud-outline"
            />
          </v-col>
          <v-col cols="12" lg="6">
            <v-text-field
              v-model="form.model"
              :disabled="loading"
              :label="isCompatible ? 'Model' : 'Model (optional)'"
              :placeholder="defaultModel"
              :rules="isCompatible ? [required('Model')] : []"
              :hint="isCompatible ? undefined : `Leave blank to use ${defaultModel}`"
              :persistent-hint="!isCompatible"
              prepend-inner-icon="mdi-chip"
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
            />
          </v-col>
          <v-col v-else cols="12" lg="6">
            <v-select
              v-model="form.reasoning_effort"
              :disabled="loading"
              :items="effortOptions"
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
        </v-row>
      </v-container>
    </v-card-text>

    <v-divider />

    <v-card-actions class="pa-4 flex-wrap">
      <v-spacer />
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
import { computed, onMounted, reactive, ref } from 'vue'
import api from '@/services/api'

const emit = defineEmits(['notification'])

const effortOptions = ['low', 'medium', 'high', 'xhigh', 'max']
const blank = () => ({
  provider: 'openai',
  model: '',
  base_url: '',
  supports_vision: true,
  reasoning_effort: 'low',
})

const form = reactive(blank())
const saved = ref(null)
const providers = ref({})
const loading = ref(false)
const loadError = ref('')

const isCompatible = computed(() => form.provider === 'openai_compatible')
const defaultModel = computed(() => providers.value[form.provider]?.default_model || '')
const providerItems = computed(() =>
  Object.entries(providers.value).map(([value, { name }]) => ({ value, title: name })),
)

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

const isChanged = computed(() => JSON.stringify(payload()) !== JSON.stringify(saved.value))
const isValid = computed(
  () =>
    !isCompatible.value ||
    (required('Model')(form.model) === true && validateUrl(form.base_url) === true),
)

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

const reset = () => apply({ ...saved.value, providers: providers.value })

const load = async () => {
  loadError.value = ''
  loading.value = true
  try {
    apply((await api.get('/api/admin/configuration/strixy')).data)
  } catch {
    loadError.value = 'Failed to load Strixy settings. Please try again.'
  } finally {
    loading.value = false
  }
}

const errorText = (error) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
  return 'Failed to save Strixy settings. Please try again.'
}

const save = async () => {
  loading.value = true
  try {
    apply((await api.put('/api/admin/configuration/strixy', payload())).data)
    emit('notification', { text: 'Strixy settings saved successfully!', color: 'success' })
  } catch (error) {
    console.error('Error saving Strixy settings:', error)
    emit('notification', { text: errorText(error), color: 'error' })
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
