<template>
  <v-dialog
    v-model="dialog"
    max-width="600px"
    persistent
    @keydown.esc="handleCancel"
  >
    <v-card>
      <!-- Header -->
      <v-card-title class="d-flex align-center pa-4 bg-primary text-white">
        <v-icon :icon="categoryIcon" class="me-3" />
        <div class="flex-grow-1">
          <div class="text-h6">Execute Hunt</div>
          <div class="text-subtitle-2 opacity-75">{{ hunt?.display_name }}</div>
        </div>
        <v-btn
          icon="mdi-close"
          variant="text"
          color="white"
          @click="handleCancel"
          :disabled="executing"
        />
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-4">
        <!-- Hunt Description -->
        <div class="mb-4">
          <div class="text-body-1 mb-2">{{ hunt?.description }}</div>
          <div class="d-flex align-center text-caption text-medium-emphasis">
            <v-icon icon="mdi-play-box-multiple" size="small" class="me-1" />
            {{ hunt?.step_count || 0 }} steps
            <v-divider vertical class="mx-2" />
            <v-icon icon="mdi-tag" size="small" class="me-1" />
            {{ hunt?.category }}
          </div>
        </div>

        <!-- Case Selection -->
        <div v-if="!caseId" class="mb-4">
          <v-select
            v-model="selectedCaseId"
            :items="caseOptions"
            item-title="title"
            item-value="id"
            label="Select Case"
            variant="outlined"
            density="comfortable"
            :rules="[rules.required]"
            prepend-icon="mdi-folder"
          >
            <template #item="{ props, item }">
              <v-list-item v-bind="props">
                <template #title>
                  <div class="d-flex align-center">
                    <span>{{ item.raw.case_number }}</span>
                    <span v-if="item.raw.title" class="text-medium-emphasis ml-2">
                      - {{ item.raw.title }}
                    </span>
                  </div>
                </template>
                <template #subtitle>
                  {{ item.raw.client?.name || 'No client' }}
                </template>
              </v-list-item>
            </template>
          </v-select>
        </div>

        <!-- Parameters Form -->
        <div v-if="hunt?.initial_parameters" class="mb-4">
          <div class="text-h6 mb-3">Hunt Parameters</div>
          
          <HuntParameterForm
            :parameters="hunt.initial_parameters"
            v-model="parameterValues"
            :errors="parameterErrors"
            @validate="handleParameterValidation"
          />
        </div>

        <!-- Error Display -->
        <v-alert v-if="error" type="error" class="mb-4">
          {{ error }}
        </v-alert>
      </v-card-text>

      <!-- Actions -->
      <v-card-actions class="pa-4 pt-0">
        <v-spacer />
        <v-btn
          variant="text"
          @click="handleCancel"
          :disabled="executing"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="elevated"
          @click="handleExecute"
          :loading="executing"
          :disabled="!isFormValid"
        >
          <v-icon icon="mdi-play" start />
          Execute Hunt
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import HuntParameterForm from './HuntParameterForm.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  hunt: {
    type: Object,
    default: null
  },
  caseId: {
    type: Number,
    default: null
  },
  cases: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'execute', 'cancel'])

// Local state
const executing = ref(false)
const error = ref(null)
const selectedCaseId = ref(props.caseId)
const parameterValues = ref({})
const parameterErrors = ref({})
const isParametersValid = ref(true)

// Computed properties
const dialog = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const categoryIcon = computed(() => {
  const iconMap = {
    person: 'mdi-account',
    domain: 'mdi-web',
    company: 'mdi-office-building',
    ip: 'mdi-ip-network',
    phone: 'mdi-phone',
    email: 'mdi-email',
    general: 'mdi-magnify'
  }
  return iconMap[props.hunt?.category] || iconMap.general
})

const caseOptions = computed(() => {
  return props.cases.map(case_ => ({
    id: case_.id,
    title: case_.title || `Case ${case_.case_number}`,
    case_number: case_.case_number,
    client: case_.client
  }))
})

const isFormValid = computed(() => {
  const hasValidCase = props.caseId || selectedCaseId.value
  return hasValidCase && isParametersValid.value
})

const rules = {
  required: value => !!value || 'This field is required'
}

// Methods
const handleExecute = async () => {
  if (!isFormValid.value) return

  try {
    executing.value = true
    error.value = null

    const targetCaseId = props.caseId || selectedCaseId.value
    
    await emit('execute', {
      huntId: props.hunt.id,
      caseId: targetCaseId,
      parameters: parameterValues.value
    })

    // Close modal on successful execution
    dialog.value = false
    
  } catch (err) {
    error.value = err.message || 'Failed to execute hunt'
    console.error('Hunt execution error:', err)
  } finally {
    executing.value = false
  }
}

const handleCancel = () => {
  if (!executing.value) {
    dialog.value = false
    emit('cancel')
  }
}

const handleParameterValidation = (isValid, errors) => {
  isParametersValid.value = isValid
  parameterErrors.value = errors
}

const resetForm = () => {
  selectedCaseId.value = props.caseId
  parameterValues.value = {}
  parameterErrors.value = {}
  isParametersValid.value = true
  error.value = null
  executing.value = false
}

// Watchers
watch(() => props.hunt, (newHunt) => {
  if (newHunt) {
    // Initialize parameter values with defaults
    const initialValues = {}
    if (newHunt.initial_parameters) {
      Object.keys(newHunt.initial_parameters).forEach(key => {
        const param = newHunt.initial_parameters[key]
        if (param.default !== undefined) {
          initialValues[key] = param.default
        } else {
          initialValues[key] = ''
        }
      })
    }
    parameterValues.value = initialValues
  }
}, { immediate: true })

watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    nextTick(() => {
      resetForm()
    })
  }
})

watch(() => props.caseId, (newCaseId) => {
  selectedCaseId.value = newCaseId
})
</script>

<style scoped>
.v-dialog > .v-card {
  overflow: visible;
}
</style>