<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="pluginDescription" />

    <v-radio-group v-model="searchType" inline density="compact">
      <template #label>
        <span class="text-subtitle2">Search Type</span>
      </template>
      <v-radio label="Person Search" value="person" />
      <v-radio label="Company Search" value="company" />
    </v-radio-group>

    <div v-if="searchType === 'person'" class="d-flex flex-column ga-3">
      <v-text-field
        v-model="localParams.email"
        label="Email Address"
        placeholder="john.doe@example.com"
        density="compact"
        hint="Primary identifier for person search"
        persistent-hint
        @update:model-value="updateParams"
      />

      <v-text-field
        v-model="localParams.name"
        label="Full Name"
        placeholder="John Doe"
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
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />

        <v-text-field
          v-model="localParams.company"
          label="Company"
          placeholder="Company name"
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
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />

        <v-text-field
          v-model="localParams.linkedin"
          label="LinkedIn Profile"
          placeholder="linkedin.com/in/johndoe"
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />
      </div>
    </div>

    <div v-if="searchType === 'company'" class="d-flex flex-column ga-3">
      <v-text-field
        v-model="localParams.name"
        label="Company Name"
        placeholder="People Data Labs"
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
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />

        <v-text-field
          v-model="localParams.domain"
          label="Domain"
          placeholder="company.com"
          density="compact"
          class="flex-grow-1"
          @update:model-value="updateParams"
        />
      </div>

      <v-text-field
        v-model="localParams.linkedin"
        label="LinkedIn Company Profile"
        placeholder="linkedin.com/company/peopledatalabs"
        density="compact"
        @update:model-value="updateParams"
      />
    </div>

    <v-alert density="compact" type="info" variant="text">
      <div v-if="searchType === 'person'">
        <strong>Person Search:</strong> At least one field is required (email, name, phone, company,
        location, or LinkedIn). <br /><strong>Best Results:</strong> Use email or LinkedIn profile
        for most accurate matches.
      </div>
      <div v-else-if="searchType === 'company'">
        <strong>Company Search:</strong> At least one field is required (name, website, domain, or
        LinkedIn). <br /><strong>Best Results:</strong> Use company website or LinkedIn profile for
        most accurate matches.
      </div>
      <div v-else>Please select a search type above to get started.</div>
    </v-alert>

    <CaseEvidenceToggle
      :model-value="props.modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
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
    search_type: 'person',
    email: '',
    phone: '',
    name: '',
    company: '',
    website: '',
    domain: '',
    location: '',
    linkedin: '',
  },
})

const searchType = computed({
  get: () => localParams.search_type,
  set: (value) => {
    localParams.search_type = value
    updateParams()
  },
})
</script>
