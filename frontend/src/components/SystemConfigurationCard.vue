<template>
  <v-card class="mb-6" variant="outlined">
    <v-card-title class="d-flex align-center pa-4 bg-surface">
      <v-icon icon="mdi-format-list-numbered" color="primary" size="large" class="me-3" />
      <div>
        <div class="text-h6 font-weight-bold">Case Number Configuration</div>
        <div class="text-body-2 text-medium-emphasis">Configure how case numbers are generated</div>
      </div>
    </v-card-title>

    <v-divider />

    <v-card-text class="pa-4">
      <v-container fluid class="pa-0">
        <v-row>
          <v-col cols="12" lg="6">
            <v-select
              v-model="selectedTemplate"
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
              label="Prefix (2-8 letters/numbers)"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-alphabetical-variant"
              :rules="[validatePrefix]"
              @input="onPrefixChange"
              hint="Enter 2-8 alphanumeric characters"
              persistent-hint
            />
          </v-col>
        </v-row>

        <v-row v-if="exampleCaseNumber">
          <v-col cols="12">
            <v-card variant="tonal" color="secondary" class="pa-4">
              <div class="d-flex align-center">
                <v-icon icon="mdi-eye" color="info" class="me-3" />
                <div>
                  <div class="text-subtitle-2 font-weight-bold text-info">Preview</div>
                  <div class="text-body-2">
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

    <v-card-actions class="pa-4">
      <v-spacer />
      <v-btn
        variant="text"
        prepend-icon="mdi-refresh"
        @click="resetConfiguration"
        :disabled="configLoading"
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
import { onMounted } from 'vue'
import { useSystemConfiguration } from '@/composables/useSystemConfiguration'

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
  resetConfiguration
} = useSystemConfiguration()

const handleSave = async () => {
  try {
    await saveConfiguration()
    emit('notification', { text: 'Configuration saved successfully!', color: 'success' })
  } catch (error) {
    console.error('Error saving configuration:', error)
    emit('notification', { text: 'Failed to save configuration. Please try again.', color: 'error' })
  }
}

onMounted(async () => {
  try {
    await loadConfiguration()
  } catch (error) {
    console.error('Error loading configuration:', error)
  }
})
</script>