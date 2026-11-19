<template>
  <v-card :elevation="0" class="configuration-workspace" variant="flat">
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <div>
        <h2 class="text-title-large font-weight-bold">Case numbering</h2>
        <div class="text-body-medium text-medium-emphasis">
          Configure how case numbers are generated
        </div>
      </div>
    </v-card-title>

    <v-divider />

    <v-card-text class="pa-4">
      <v-progress-linear v-if="configLoading" indeterminate aria-label="Loading configuration" />
      <v-alert v-if="loadError" type="error" variant="tonal" class="mb-4">
        {{ loadError }}
        <v-btn variant="text" @click="load">Retry</v-btn>
      </v-alert>
      <v-container v-else fluid class="pa-0">
        <v-row>
          <v-col cols="12" lg="6">
            <v-select
              v-model="selectedTemplate"
              :disabled="configLoading || !!loadError"
              :items="templateOptions"
              item-title="display_name"
              item-value="value"
              label="Case Number Format"
              prepend-inner-icon="mdi-format-list-numbered"
              @update:model-value="onTemplateChange"
            />
          </v-col>

          <v-col cols="12" lg="6" v-if="selectedTemplate === 'PREFIX-YYMM-NN'">
            <v-text-field
              v-model="caseNumberPrefix"
              :disabled="configLoading || !!loadError"
              label="Prefix (2-8 letters/numbers)"
              prepend-inner-icon="mdi-alphabetical-variant"
              :rules="[validatePrefix]"
              @update:model-value="updatePreview"
              hint="Enter 2-8 alphanumeric characters"
              persistent-hint
            />
          </v-col>
        </v-row>

        <v-row v-if="exampleCaseNumber">
          <v-col cols="12">
            <v-card :elevation="0" variant="outlined" class="pa-4">
              <div class="d-flex align-center">
                <v-icon icon="mdi-eye" color="info" class="me-3" />
                <div>
                  <div class="text-title-small font-weight-bold">Preview</div>
                  <div class="text-body-medium">
                    Next case will be numbered in the format:
                    <v-chip color="primary" variant="elevated" class="ml-2">
                      {{ exampleCaseNumber }}
                    </v-chip>
                  </div>
                </div>
              </div>
            </v-card>
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
        @click="resetConfiguration"
        :disabled="configLoading || !!loadError"
      >
        Reset
      </v-btn>
      <v-btn
        color="primary"
        prepend-icon="mdi-content-save"
        :loading="configLoading"
        :disabled="!isConfigChanged || !isConfigValid || configLoading || !!loadError"
        @click="save"
      >
        Save Configuration
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '@/services/api'

const emit = defineEmits(['notification'])

const templateOptions = [
  { display_name: 'Monthly Reset (YYMM-NN)', value: 'YYMM-NN' },
  { display_name: 'Prefix + Monthly Reset (PREFIX-YYMM-NN)', value: 'PREFIX-YYMM-NN' },
]

const selectedTemplate = ref('YYMM-NN')
const caseNumberPrefix = ref('')
const saved = ref({ template: 'YYMM-NN', prefix: '' })
const configLoading = ref(false)
const loadError = ref('')
const exampleCaseNumber = ref('')

const isConfigChanged = computed(
  () =>
    selectedTemplate.value !== saved.value.template ||
    caseNumberPrefix.value !== saved.value.prefix,
)

const validatePrefix = (value) => {
  if (selectedTemplate.value === 'PREFIX-YYMM-NN') {
    if (!value) return 'Prefix is required'
    if (!/^[A-Za-z0-9]{2,8}$/.test(value)) return 'Prefix must be 2-8 alphanumeric characters'
  }
  return true
}
const isConfigValid = computed(() => validatePrefix(caseNumberPrefix.value) === true)

const updatePreview = async () => {
  if (!isConfigValid.value) {
    exampleCaseNumber.value = ''
    return
  }
  try {
    const params = new URLSearchParams({ template: selectedTemplate.value })
    if (selectedTemplate.value === 'PREFIX-YYMM-NN' && caseNumberPrefix.value) {
      params.append('prefix', caseNumberPrefix.value)
    }
    const response = await api.get(`/api/admin/configuration/preview?${params}`)
    exampleCaseNumber.value = response.data.example_case_number
  } catch (error) {
    console.error('Error updating preview:', error)
    exampleCaseNumber.value = ''
  }
}

const onTemplateChange = () => {
  if (selectedTemplate.value !== 'PREFIX-YYMM-NN') caseNumberPrefix.value = ''
  return updatePreview()
}

const resetConfiguration = () => {
  selectedTemplate.value = saved.value.template
  caseNumberPrefix.value = saved.value.prefix
  return updatePreview()
}

const load = async () => {
  loadError.value = ''
  configLoading.value = true
  try {
    const { data } = await api.get('/api/admin/configuration')
    saved.value = { template: data.case_number_template, prefix: data.case_number_prefix || '' }
    await resetConfiguration()
  } catch {
    loadError.value = 'Failed to load case numbering. Please try again.'
  } finally {
    configLoading.value = false
  }
}

const save = async () => {
  if (!isConfigValid.value) return
  configLoading.value = true
  try {
    await api.put('/api/admin/configuration', {
      case_number_template: selectedTemplate.value,
      case_number_prefix:
        selectedTemplate.value === 'PREFIX-YYMM-NN' ? caseNumberPrefix.value : null,
    })
    saved.value = { template: selectedTemplate.value, prefix: caseNumberPrefix.value }
    emit('notification', { text: 'Configuration saved successfully!', color: 'success' })
  } catch (error) {
    console.error('Error saving configuration:', error)
    emit('notification', {
      text: 'Failed to save configuration. Please try again.',
      color: 'error',
    })
  } finally {
    configLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.configuration-workspace {
  max-width: 900px;
}
</style>
