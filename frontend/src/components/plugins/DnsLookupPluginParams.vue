<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <!-- Lookup Mode -->
    <v-radio-group
      v-model="lookupMode"
      inline
      density="compact"
      @update:model-value="updateMode"
    >
      <template #label>
        <span class="text-subtitle2">Lookup Type</span>
      </template>
      <v-radio label="Forward DNS (Domain → IP)" value="forward" />
      <v-radio label="Reverse DNS (IP → Domain)" value="reverse" />
    </v-radio-group>

    <!-- Input Field -->
    <v-text-field
      v-model="localParams.domain"
      :label="inputLabel"
      :placeholder="inputPlaceholder"
      variant="outlined"
      density="compact"
      @update:model-value="updateParams"
    />

    <!-- Record Types (only for forward DNS) -->
    <v-select
      v-if="lookupMode === 'forward'"
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

    <!-- Case Evidence Toggle -->
    <CaseEvidenceToggle
      :model-value="props.modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />

  </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import CaseEvidenceToggle from './CaseEvidenceToggle.vue'

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

// Lookup mode state
const lookupMode = ref(props.modelValue.lookup_mode || 'forward')

// Dynamic input labels based on mode
const inputLabel = computed(() => {
  return lookupMode.value === 'forward' ? 'Domain Names' : 'IP Addresses'
})

const inputPlaceholder = computed(() => {
  return lookupMode.value === 'forward' 
    ? 'Enter domain names (e.g., google.com, github.com)'
    : 'Enter IP addresses (e.g., 8.8.8.8, 1.1.1.1)'
})

// Local parameter state for plugin-specific params
const localParams = reactive({
  domain: props.modelValue.domain || '',
  timeout: props.modelValue.timeout || 5.0,
  nameservers: props.modelValue.nameservers || '',
  lookup_mode: lookupMode.value
})

// Selected record types as array
const selectedRecordTypes = ref(
  props.modelValue.record_types 
    ? props.modelValue.record_types.split(',').map(t => t.trim())
    : ['A']
)

// Update mode and clear inappropriate parameters
const updateMode = () => {
  localParams.lookup_mode = lookupMode.value
  
  if (lookupMode.value === 'reverse') {
    // For reverse DNS, we don't need record types (only PTR)
    delete localParams.record_types
  } else {
    // For forward DNS, ensure we have record types
    updateRecordTypes()
  }
  
  updateParams()
}

// Update record types parameter when selection changes
const updateRecordTypes = () => {
  if (lookupMode.value === 'forward') {
    localParams.record_types = selectedRecordTypes.value.join(',')
  }
  updateParams()
}

// Emit parameter updates for plugin-specific params
const updateParams = () => {
  emit('update:modelValue', { 
    ...props.modelValue,
    ...localParams 
  })
}

// Initialize record_types on mount for forward mode
if (lookupMode.value === 'forward' && !localParams.record_types) {
  updateRecordTypes()
}

// Watch for external changes to modelValue
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, {
    domain: newValue.domain || '',
    timeout: newValue.timeout || 5.0,
    nameservers: newValue.nameservers || '',
    lookup_mode: newValue.lookup_mode || 'forward'
  })
  
  // Update lookup mode
  if (newValue.lookup_mode) {
    lookupMode.value = newValue.lookup_mode
  }
  
  // Update record types if in forward mode
  if (newValue.record_types && lookupMode.value === 'forward') {
    selectedRecordTypes.value = newValue.record_types.split(',').map(t => t.trim())
  }
}, { deep: true })
</script>