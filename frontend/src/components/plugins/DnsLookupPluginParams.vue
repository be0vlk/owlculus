<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <v-radio-group v-model="lookupMode" density="compact" inline>
      <template #label>
        <span class="text-subtitle2">Lookup Type</span>
      </template>
      <v-radio label="Forward DNS (Domain → IP)" value="forward" />
      <v-radio label="Reverse DNS (IP → Domain)" value="reverse" />
    </v-radio-group>

    <v-text-field
      v-model="localParams.domain"
      :label="inputLabel"
      :placeholder="inputPlaceholder"
      density="compact"
      @update:model-value="updateParams"
    />

    <v-select
      v-if="lookupMode === 'forward'"
      v-model="selectedRecordTypes"
      label="Record Types"
      hint="Select DNS record types to query"
      :items="dnsRecordTypes"
      multiple
      chips
      persistent-hint
      density="compact"
      @update:model-value="updateParams"
    />

    <v-text-field
      v-model.number="localParams.timeout"
      label="Timeout"
      placeholder="Query timeout in seconds"
      type="number"
      density="compact"
      @update:model-value="updateParams"
    />

    <v-text-field
      v-model="localParams.nameservers"
      label="Custom Nameservers (Optional)"
      placeholder="Comma-separated custom DNS servers (e.g., 8.8.8.8,1.1.1.1)"
      density="compact"
      @update:model-value="updateParams"
    />

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
    required: true,
  },
  modelValue: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])

const { pluginDescription, localParams, updateParams } = usePluginParamsAdvanced(props, emit, {
  parameterDefaults: {
    domain: '',
    timeout: 5.0,
    nameservers: '',
    lookup_mode: 'forward',
  },
  customUpdateLogic: (updatedValue, params) => {
    if (params.lookup_mode === 'reverse') {
      delete updatedValue.record_types
    } else if (selectedRecordTypes.value && params.lookup_mode === 'forward') {
      updatedValue.record_types = selectedRecordTypes.value.join(',')
    }
  },
})

const dnsRecordTypes = [
  { title: 'A Records (IPv4)', value: 'A' },
  { title: 'AAAA Records (IPv6)', value: 'AAAA' },
  { title: 'MX Records (Mail Exchange)', value: 'MX' },
  { title: 'TXT Records (Text)', value: 'TXT' },
  { title: 'NS Records (Name Server)', value: 'NS' },
  { title: 'CNAME Records (Canonical Name)', value: 'CNAME' },
]

const lookupMode = computed({
  get: () => localParams.lookup_mode,
  set: (value) => {
    localParams.lookup_mode = value
    updateParams()
  },
})

const inputLabel = computed(() => {
  return lookupMode.value === 'forward' ? 'Domain Names' : 'IP Addresses'
})

const inputPlaceholder = computed(() => {
  return lookupMode.value === 'forward'
    ? 'Enter domain names (e.g., google.com, github.com)'
    : 'Enter IP addresses (e.g., 8.8.8.8, 1.1.1.1)'
})

const selectedRecordTypes = ref(
  props.modelValue.record_types
    ? props.modelValue.record_types.split(',').map((t) => t.trim())
    : ['A'],
)

watch(
  () => props.modelValue.record_types,
  (newValue) => {
    if (newValue && lookupMode.value === 'forward') {
      selectedRecordTypes.value = newValue.split(',').map((t) => t.trim())
    }
  },
)

if (lookupMode.value === 'forward' && !props.modelValue.record_types) {
  updateParams()
}
</script>
