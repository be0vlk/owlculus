<template>
  <div class="d-flex flex-column ga-3">
    <PluginDescriptionCard :description="parameters.description || ''" />
    <p>Scan entities in the active case for matches across accessible cases.</p>
    <CaseEvidenceToggle
      :model-value="modelValue"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>

<script setup>
import PluginDescriptionCard from './PluginDescriptionCard.vue'
import CaseEvidenceToggle from './CaseEvidenceToggle.vue'

defineProps({
  parameters: { type: Object, required: true },
  modelValue: { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue'])
</script>
