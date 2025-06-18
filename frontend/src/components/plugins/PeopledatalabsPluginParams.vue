<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />
    
    <!-- API Key Warning -->
    <ApiKeyWarning
      v-if="missingApiKeys.length > 0"
      :missing-providers="missingApiKeys"
    />

    <!-- Search Type Selection -->
    <v-radio-group
      v-model="searchType"
      inline
      density="compact"
      @update:model-value="updateSearchType"
    >
      <template #label>
        <span class="text-subtitle2">Search Type</span>
      </template>
      <v-radio label="Person Search" value="person" />
      <v-radio label="Company Search" value="company" />
    </v-radio-group>

    <!-- Person Search Fields -->
    <div v-if="searchType === 'person'" class="d-flex flex-column ga-3">
      <v-text-field
        v-model="localParams.email"
        label="Email Address"
        placeholder="john.doe@example.com"
        variant="outlined"
        density="compact"
        hint="Primary identifier for person search"
        persistent-hint
        @update:model-value="updateParams"
      />
      
      <v-text-field
        v-model="localParams.name"
        label="Full Name"
        placeholder="John Doe"
        variant="outlined"
        density="compact"
        hint="Person's full name"
        persistent-hint
        @update:model-value="updateParams"
      />

      <div class="d-flex ga-3">
        <v-text-field
          v-model="localParams.phone"
          label="Phone Number"
          placeholder="+1234567890"
          variant="outlined"
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />
        
        <v-text-field
          v-model="localParams.company"
          label="Company"
          placeholder="Company name"
          variant="outlined"
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />
      </div>

      <div class="d-flex ga-3">
        <v-text-field
          v-model="localParams.location"
          label="Location"
          placeholder="San Francisco, CA"
          variant="outlined"
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />
        
        <v-text-field
          v-model="localParams.linkedin"
          label="LinkedIn Profile"
          placeholder="linkedin.com/in/johndoe"
          variant="outlined"
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />
      </div>
    </div>

    <!-- Company Search Fields -->
    <div v-if="searchType === 'company'" class="d-flex flex-column ga-3">
      <v-text-field
        v-model="localParams.name"
        label="Company Name"
        placeholder="People Data Labs"
        variant="outlined"
        density="compact"
        hint="Primary identifier for company search"
        persistent-hint
        @update:model-value="updateParams"
      />

      <div class="d-flex ga-3">
        <v-text-field
          v-model="localParams.website"
          label="Website"
          placeholder="peopledatalabs.com"
          variant="outlined"
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />
        
        <v-text-field
          v-model="localParams.domain"
          label="Domain"
          placeholder="company.com"
          variant="outlined"
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />
      </div>

      <v-text-field
        v-model="localParams.linkedin"
        label="LinkedIn Company Profile"
        placeholder="linkedin.com/company/peopledatalabs"
        variant="outlined"
        density="compact"
        @update:model-value="updateParams"
      />
    </div>

    <!-- Search Requirements Info -->
    <v-alert
      type="info"
      variant="text"
      density="compact"
    >
      <div v-if="searchType === 'person'">
        <strong>Person Search:</strong> At least one field is required (email, name, phone, company, location, or LinkedIn).
        <br><strong>Best Results:</strong> Use email or LinkedIn profile for most accurate matches.
      </div>
      <div v-else-if="searchType === 'company'">
        <strong>Company Search:</strong> At least one field is required (name, website, domain, or LinkedIn).
        <br><strong>Best Results:</strong> Use company website or LinkedIn profile for most accurate matches.
      </div>
      <div v-else>
        Please select a search type above to get started.
      </div>
    </v-alert>

    <!-- Case Evidence Toggle -->
    <CaseEvidenceToggle
      :model-value="props.modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />

  </div>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted } from 'vue'
import { usePluginApiKeys } from '@/composables/usePluginApiKeys'
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import ApiKeyWarning from './ApiKeyWarning.vue'
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

// Search type state
const searchType = ref(props.modelValue.search_type || 'person')

// Local parameter state for plugin-specific params
const localParams = reactive({
  search_type: searchType.value,
  email: props.modelValue.email || '',
  phone: props.modelValue.phone || '',
  name: props.modelValue.name || '',
  company: props.modelValue.company || '',
  website: props.modelValue.website || '',
  domain: props.modelValue.domain || '',
  location: props.modelValue.location || '',
  linkedin: props.modelValue.linkedin || ''
})

// Use plugin API keys composable
const { checkPluginApiKeys, getMissingApiKeys } = usePluginApiKeys()
const missingApiKeys = ref([])

// Check API keys on mount
onMounted(async () => {
  // Check if plugin has API key requirements
  if (props.parameters.api_key_requirements && props.parameters.api_key_requirements.length > 0) {
    const plugin = {
      name: 'PeopledatalabsPlugin',
      api_key_requirements: props.parameters.api_key_requirements
    }
    await checkPluginApiKeys(plugin)
    missingApiKeys.value = getMissingApiKeys(plugin)
  }
})

// Update search type and related parameters
const updateSearchType = () => {
  localParams.search_type = searchType.value
  updateParams()
}

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
    search_type: newValue.search_type || 'person',
    email: newValue.email || '',
    phone: newValue.phone || '',
    name: newValue.name || '',
    company: newValue.company || '',
    website: newValue.website || '',
    domain: newValue.domain || '',
    location: newValue.location || '',
    linkedin: newValue.linkedin || ''
  })
  
  // Update search type
  if (newValue.search_type) {
    searchType.value = newValue.search_type
  }
}, { deep: true })
</script>