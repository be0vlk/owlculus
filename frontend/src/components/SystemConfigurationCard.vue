<template>
  <v-card
    :class="[embedded ? 'admin-embedded' : 'mb-6', { 'configuration-workspace': embedded }]"
    :variant="embedded ? 'flat' : 'outlined'"
  >
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <v-icon
        v-if="!embedded"
        icon="mdi-format-list-numbered"
        color="primary"
        size="large"
        class="me-3"
      />
      <div>
        <h2 class="text-title-large font-weight-bold">
          {{ embedded ? 'Case numbering' : 'Case Number Configuration' }}
        </h2>
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
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-format-list-numbered"
              @update:model-value="onTemplateChange"
            />
          </v-col>

          <v-col cols="12" lg="6" v-if="selectedTemplate === 'PREFIX-YYMM-NN'">
            <v-text-field
              v-model="caseNumberPrefix"
              :disabled="configLoading || !!loadError"
              label="Prefix (2-8 letters/numbers)"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-alphabetical-variant"
              :rules="[validatePrefix]"
              @update:model-value="onPrefixChange"
              hint="Enter 2-8 alphanumeric characters"
              persistent-hint
            />
          </v-col>
        </v-row>

        <v-row v-if="exampleCaseNumber">
          <v-col cols="12">
            <v-card variant="outlined" class="pa-4">
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
        variant="flat"
        prepend-icon="mdi-content-save"
        :loading="configLoading"
        :disabled="!isConfigChanged || !isConfigValid"
        @click="handleSave"
      >
        Save Configuration
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
defineProps({ embedded: Boolean })
import { onMounted, ref } from 'vue'
import { useSystemConfiguration } from '@/composables/useSystemConfiguration'

const loadError = ref('')

const emit = defineEmits(['notification'])

const {
  // State
  selectedTemplate,
  caseNumberPrefix,
  configLoading,
  exampleCaseNumber,

  // Constants
  templateOptions,

  // Computed
  isConfigChanged,
  isConfigValid,

  // Validation
  validatePrefix,

  // Methods
  onTemplateChange,
  onPrefixChange,
  loadConfiguration,
  saveConfiguration,
  resetConfiguration,
} = useSystemConfiguration()

const handleSave = async () => {
  try {
    if (!(await saveConfiguration())) return
    emit('notification', { text: 'Configuration saved successfully!', color: 'success' })
  } catch (error) {
    console.error('Error saving configuration:', error)
    emit('notification', {
      text: 'Failed to save configuration. Please try again.',
      color: 'error',
    })
  }
}

const load = async () => {
  loadError.value = ''
  configLoading.value = true
  try {
    await loadConfiguration()
  } catch {
    loadError.value = 'Failed to load case numbering. Please try again.'
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
