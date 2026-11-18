<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="parameters.description || ''" />
    <v-alert v-if="otherCases === 0" type="info" variant="tonal">
      There are no other cases you can access, so there is nothing to compare against.
    </v-alert>
    <p v-else-if="activeCase">
      Scans the entities in Case #{{ activeCase.case_number }} against the {{ otherCases }} other
      {{ otherCases === 1 ? 'case' : 'cases' }} you can access.
    </p>
    <CaseEvidenceToggle
      :model-value="modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import CaseEvidenceToggle from './CaseEvidenceToggle.vue'
import { useActiveCaseStore } from '@/stores/activeCase'

defineProps({
  parameters: { type: Object, required: true },
  modelValue: { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue'])

const { activeCase, accessibleCases } = storeToRefs(useActiveCaseStore())
const otherCases = computed(() => (activeCase.value ? accessibleCases.value.length - 1 : null))
</script>
