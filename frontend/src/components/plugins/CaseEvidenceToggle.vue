<template>
  <v-switch
    :model-value="modelValue.save_to_case === true"
    label="Save to case evidence"
    hint="Saved output belongs to the active case."
    persistent-hint
    color="primary"
    density="compact"
    @update:model-value="updateSaving"
  />
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue'])

const updateSaving = (saveToCase) => {
  const params = { ...props.modelValue, save_to_case: saveToCase }
  delete params.case_id
  emit('update:modelValue', params)
}
</script>
