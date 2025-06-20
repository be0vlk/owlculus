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
import { ref, computed, watch } from 'vue'
import { usePluginParamsAdvanced } from '@/composables/usePluginParams'
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

// Use advanced plugin params composable
const {
  pluginDescription,
  localParams,
  updateParams
} = usePluginParamsAdvanced(props, emit, {
  parameterDefaults: {
    domain: '',
    timeout: 5.0,
    nameservers: '',
    lookup_mode: 'forward'
  },
  customUpdateLogic: (updatedValue, params) => {
    // Handle record_types based on lookup mode
    if (params.lookup_mode === 'reverse') {
      delete updatedValue.record_types
    } else if (selectedRecordTypes.value && params.lookup_mode === 'forward') {
      updatedValue.record_types = selectedRecordTypes.value.join(',')
    }
  }
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

// Lookup mode state (computed from localParams)
const lookupMode = computed({
  get: () => localParams.lookup_mode,
  set: (value) => {
    localParams.lookup_mode = value
    updateMode()
  }
})

// Dynamic input labels based on mode
const inputLabel = computed(() => {
  return lookupMode.value === 'forward' ? 'Domain Names' : 'IP Addresses'
})

const inputPlaceholder = computed(() => {
  return lookupMode.value === 'forward' 
    ? 'Enter domain names (e.g., google.com, github.com)'
    : 'Enter IP addresses (e.g., 8.8.8.8, 1.1.1.1)'
})

// Selected record types as array
const selectedRecordTypes = ref(
  props.modelValue.record_types 
    ? props.modelValue.record_types.split(',').map(t => t.trim())
    : ['A']
)

// Update mode and clear inappropriate parameters
const updateMode = () => {
  updateParams()
}

// Update record types parameter when selection changes
const updateRecordTypes = () => {
  updateParams()
}

// Watch for external changes to record_types
watch(() => props.modelValue.record_types, (newValue) => {
  if (newValue && lookupMode.value === 'forward') {
    selectedRecordTypes.value = newValue.split(',').map(t => t.trim())
  }
})

// Initialize record_types on mount for forward mode
if (lookupMode.value === 'forward' && !props.modelValue.record_types) {
  updateRecordTypes()
}
</script>