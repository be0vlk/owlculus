<template>
  <v-dialog
    v-model="dialog"
    max-width="600px"
    scrollable
    aria-label="Execute Hunt"
    persistent
    @keydown.esc="handleCancel"
  >
    <v-card>
      <!-- Header -->
      <v-card-title class="d-flex align-center pa-4 bg-primary text-white">
        <v-icon :icon="categoryIcon" class="me-3" />
        <div class="flex-grow-1">
          <div class="text-title-large">Execute Hunt</div>
          <div class="text-title-small opacity-75">{{ hunt?.display_name }}</div>
        </div>
        <v-btn
          icon="mdi-close"
          aria-label="Close hunt configuration"
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
          <div class="text-body-large mb-2">{{ hunt?.description }}</div>
          <div class="d-flex align-center text-body-small text-medium-emphasis">
            <v-icon icon="mdi-play-box-multiple" size="small" class="me-1" />
            {{ hunt?.step_count || 0 }} steps
            <v-divider vertical class="mx-2" />
            <v-icon icon="mdi-tag" size="small" class="me-1" />
            {{ hunt?.category }}
          </div>
        </div>

        <!-- Parameters Form -->
        <div v-if="hunt" class="mb-4">
          <div class="text-title-large mb-3">Hunt Parameters</div>

          <HuntParameterForm
            ref="parameterForm"
            :id="parameterFormId"
            @submit="handleExecute"
            :parameters="hunt.initial_parameters || {}"
            :disabled="executing"
            v-model="parameterValues"
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
        <v-btn :disabled="executing" variant="text" @click="handleCancel"> Cancel </v-btn>
        <v-btn
          color="primary"
          variant="elevated"
          type="submit"
          :form="parameterFormId"
          :loading="executing"
          :disabled="!isFormValid || executing"
        >
          <v-icon icon="mdi-play" start />
          Execute Hunt
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, useId } from 'vue'
import HuntParameterForm from './HuntParameterForm.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  hunt: {
    type: Object,
    default: null,
  },
  caseId: {
    type: Number,
    default: null,
  },
  executing: Boolean,
  error: { type: String, default: null },
})

const emit = defineEmits(['update:modelValue', 'execute', 'cancel'])

// Local state
const parameterForm = ref(null)
const parameterFormId = useId()
const parameterValues = ref({})

// Computed properties
const dialog = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const categoryIcon = computed(() => {
  const iconMap = {
    person: 'mdi-account',
    domain: 'mdi-web',
    company: 'mdi-office-building',
    ip: 'mdi-ip-network',
    phone: 'mdi-phone',
    email: 'mdi-email',
    general: 'mdi-magnify',
  }
  return iconMap[props.hunt?.category] || iconMap.general
})

const isFormValid = computed(() => !!props.caseId)

// Methods
const handleExecute = async () => {
  if (!isFormValid.value || props.executing) return
  if (parameterForm.value && !(await parameterForm.value.validate())) return
  emit('execute', {
    huntId: props.hunt.id,
    caseId: props.caseId,
    parameters: { ...parameterValues.value },
  })
}

const handleCancel = () => {
  if (!props.executing) {
    dialog.value = false
    emit('cancel')
  }
}

watch(
  [() => props.modelValue, () => props.hunt],
  () => {
    if (props.modelValue) {
      parameterValues.value = {}
    }
  },
  { immediate: true },
)
</script>
