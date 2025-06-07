<template>
  <div class="d-flex flex-column ga-3">
    <!-- About card with plugin description (always at top) -->
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

    <v-text-field
      v-model="localParams.domain"
      label="Domain Name"
      placeholder="example.com"
      variant="outlined"
      density="compact"
      :rules="[
        v => !!v || 'Domain is required',
        v => !v || /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/.test(v.replace(/^https?:\/\//, '').split('/')[0]) || 'Invalid domain format'
      ]"
      @update:model-value="updateParams"
    />

    <v-text-field
      v-model.number="localParams.timeout"
      label="Timeout (seconds)"
      placeholder="30"
      variant="outlined"
      density="compact"
      type="number"
      @update:model-value="updateParams"
    />
  </div>
</template>

<script setup>
import { reactive, watch, computed } from 'vue'

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

// Extract plugin description from parameters
const pluginDescription = computed(() => props.parameters?.description)

// Local parameter state
const localParams = reactive({
  domain: props.modelValue.domain || '',
  timeout: props.modelValue.timeout || 30,
})

// Emit parameter updates
const updateParams = () => {
  emit('update:modelValue', { ...localParams })
}

// Watch for external changes
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, newValue)
}, { deep: true })
</script>
