<template>
  <div class="d-flex flex-column ga-3">
    <!-- About Plugin Information Card -->
    <v-card
      v-if="pluginDescription"
      color="blue-lighten-5"
      elevation="0"
      rounded="lg"
      class="pa-3"
    >
      <div class="d-flex align-center ga-2 mb-2">
        <v-icon color="blue">mdi-information</v-icon>
        <span class="text-subtitle2 font-weight-medium">About</span>
      </div>
      <p class="text-body-2 mb-0">
        {{ pluginDescription }}
      </p>
    </v-card>

    <!-- Email -->
    <v-text-field
      v-model="localParams.email"
      label="Email Address"
      placeholder="Enter email address to check for account registrations"
      variant="outlined"
      density="compact"
      type="email"
      :rules="[emailRule]"
      @update:model-value="updateParams"
    />

    <!-- Timeout -->
    <v-text-field
      v-model.number="localParams.timeout"
      label="Timeout"
      placeholder="Request timeout per platform in seconds"
      type="number"
      variant="outlined"
      density="compact"
      min="1"
      max="60"
      @update:model-value="updateParams"
    />

    <!-- Save to Case Option -->
    <v-switch
      v-model="caseParams.save_to_case"
      label="Save to case evidence"
      persistent-hint
      color="primary"
      density="compact"
      @update:model-value="updateCaseParams"
    />

    <!-- Case Selection (only when save_to_case is enabled) -->
    <v-select
      v-if="caseParams.save_to_case"
      v-model="caseParams.case_id"
      label="Case to Save Evidence To"
      :items="caseItems"
      :loading="loadingCases"
      :disabled="loadingCases"
      item-title="display_name"
      item-value="id"
      persistent-hint
      variant="outlined"
      density="compact"
      @update:model-value="updateCaseParams"
    >
      <template #prepend-item>
        <v-list-item>
          <v-list-item-title class="text-caption text-medium-emphasis">
            Only cases you have access to are shown
          </v-list-item-title>
        </v-list-item>
        <v-divider />
      </template>

      <template #no-data>
        <v-list-item>
          <v-list-item-title class="text-medium-emphasis">
            No accessible cases found
          </v-list-item-title>
        </v-list-item>
      </template>
    </v-select>

  </div>
</template>

<script setup>
import { reactive, watch, computed } from 'vue'
import { useCaseSelection } from '@/composables/useCaseSelection'

const props = defineProps({
  parameters: {
    type: Object,
    required: true
  },
  modelValue: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

// Plugin description from backend
const pluginDescription = computed(() => {
  return props.parameters?.description || ''
})

// Email validation rule
const emailRule = (value) => {
  if (!value) return 'Email address is required'
  const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return pattern.test(value) || 'Please enter a valid email address'
}

// Local parameter state for plugin-specific params
const localParams = reactive({
  email: props.modelValue.email || '',
  timeout: props.modelValue.timeout || 10.0
})

// Use case selection composable
const {
  cases,
  loadingCases,
  caseParams,
  caseItems,
  selectedCase,
  updateCaseParams,
  formatDateOnly
} = useCaseSelection(props, emit)

// Emit parameter updates for plugin-specific params
const updateParams = () => {
  emit('update:modelValue', { 
    ...props.modelValue,
    ...localParams 
  })
}

// Watch for external changes to modelValue
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, {
    email: newValue.email || '',
    timeout: newValue.timeout || 10.0
  })
}, { deep: true })
</script>