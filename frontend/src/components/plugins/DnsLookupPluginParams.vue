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
import { ref, reactive, watch, computed } from 'vue'
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

// Use case selection composable
const {
  loadingCases,
  caseParams,
  caseItems,
  updateCaseParams
} = useCaseSelection(props, emit)

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