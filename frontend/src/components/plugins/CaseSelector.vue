<template>
  <v-select
    :model-value="modelValue"
    :label="label"
    :items="caseItems"
    :loading="loadingCases"
    :disabled="loadingCases"
    item-title="display_name"
    item-value="id"
    persistent-hint
    variant="outlined"
    density="compact"
    @update:model-value="$emit('update:modelValue', $event)"
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
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { caseService } from '@/services/case'

defineProps({
  modelValue: {
    type: [String, Number],
    default: null
  },
  label: {
    type: String,
    default: 'Select Case'
  }
})

defineEmits(['update:modelValue'])

const cases = ref([])
const loadingCases = ref(true)

const caseItems = computed(() => {
  return cases.value.map(case_ => ({
    ...case_,
    display_name: `Case #${case_.case_number}: ${case_.title}`
  }))
})

const loadCases = async () => {
  try {
    loadingCases.value = true
    const response = await caseService.getCases()
    cases.value = response
  } catch (error) {
    console.error('Failed to load cases:', error)
    cases.value = []
  } finally {
    loadingCases.value = false
  }
}

onMounted(() => {
  loadCases()
})
</script>