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

    <!-- Case Selection -->
    <v-select
      v-model="localParams.case_id"
      label="Case to Scan"
      :items="caseItems"
      :loading="loadingCases"
      :disabled="loadingCases"
      item-title="display_name"
      item-value="id"
      persistent-hint
      variant="outlined"
      density="compact"
      @update:model-value="updateParams"
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

    <!-- Save to Case Option -->
    <v-switch
      v-model="localParams.save_to_case"
      label="Save to case evidence"
      persistent-hint
      color="primary"
      density="compact"
      @update:model-value="updateParams"
    />

  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { caseService } from '@/services/case'

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

// Local state
const cases = ref([])
const loadingCases = ref(true)

// Local parameter state
const localParams = reactive({
  case_id: props.modelValue.case_id || null,
  save_to_case: props.modelValue.save_to_case !== undefined ? props.modelValue.save_to_case : false
})

// Computed properties
const caseItems = computed(() => {
  return cases.value.map(case_ => ({
    ...case_,
    display_name: `Case #${case_.case_number}: ${case_.title}`
  }))
})


// Methods
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

const updateParams = () => {
  emit('update:modelValue', { ...localParams })
}


// Watch for external changes to modelValue
watch(() => props.modelValue, (newValue) => {
  Object.assign(localParams, newValue)
}, { deep: true })

// Load cases on mount
onMounted(() => {
  loadCases()
})
</script>

<style scoped>
ul {
  list-style-type: disc;
}

li {
  margin-bottom: 4px;
}
</style>
