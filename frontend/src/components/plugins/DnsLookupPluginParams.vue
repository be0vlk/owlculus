<template>
  <div class="d-flex flex-column ga-3">
    <!-- Domain -->
    <v-text-field
      v-model="localParams.domain"
      label="Domain"
      placeholder="Domain name to resolve (or comma-separated list for bulk lookup)"
      variant="outlined"
      density="compact"
      @update:model-value="updateParams"
    />

    <!-- Record Types -->
    <v-select
      v-model="selectedRecordTypes"
      label="Record Types"
      hint="Select DNS record types to query"
      :items="dnsRecordTypes"
      multiple
      chips
      persistent-hint
      variant="outlined"
      density="compact"
      @update:model-value="updateRecordTypes"
    />

    <!-- Timeout -->
    <v-text-field
      v-model.number="localParams.timeout"
      label="Timeout"
      placeholder="Query timeout in seconds"
      type="number"
      variant="outlined"
      density="compact"
      @update:model-value="updateParams"
    />

    <!-- Custom Nameservers -->
    <v-text-field
      v-model="localParams.nameservers"
      label="Custom Nameservers (Optional)"
      placeholder="Comma-separated custom DNS servers (e.g., 8.8.8.8,1.1.1.1)"
      variant="outlined"
      density="compact"
      @update:model-value="updateParams"
    />

    <!-- Use Cache -->
    <v-switch
      v-model="localParams.use_cache"
      label="Use Cache"
      hint="Use cached results if available"
      persistent-hint
      color="primary"
      density="compact"
      @update:model-value="updateParams"
    />

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
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'

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

// DNS record types
const dnsRecordTypes = [
  { title: 'A Records (IPv4)', value: 'A' },
  { title: 'AAAA Records (IPv6)', value: 'AAAA' },
  { title: 'MX Records (Mail Exchange)', value: 'MX' },
  { title: 'TXT Records (Text)', value: 'TXT' },
  { title: 'NS Records (Name Server)', value: 'NS' },
  { title: 'CNAME Records (Canonical Name)', value: 'CNAME' }
]

// Local parameter state
const localParams = reactive({
  domain: props.modelValue.domain || '',
  timeout: props.modelValue.timeout || 5.0,
  nameservers: props.modelValue.nameservers || '',
  use_cache: props.modelValue.use_cache !== undefined ? props.modelValue.use_cache : true
})

// Selected record types as array
const selectedRecordTypes = ref(
  props.modelValue.record_types 
    ? props.modelValue.record_types.split(',').map(t => t.trim())
    : ['A']
)

// Update record types parameter when selection changes
const updateRecordTypes = () => {
  localParams.record_types = selectedRecordTypes.value.join(',')
  updateParams()
}

// Emit parameter updates
const updateParams = () => {
  emit('update:modelValue', { ...localParams })
}

// Initialize record_types on mount
if (!localParams.record_types) {
  updateRecordTypes()
}

// Watch for external changes to modelValue
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, newValue)
  if (newValue.record_types) {
    selectedRecordTypes.value = newValue.record_types.split(',').map(t => t.trim())
  }
}, { deep: true })
</script>