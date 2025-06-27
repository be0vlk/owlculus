<template>
  <v-dialog
    v-model="dialog"
    max-width="800px"
    @keydown.esc="handleClose"
  >
    <v-card>
      <!-- Header -->
      <v-card-title class="d-flex align-center pa-4 bg-surface">
        <v-icon :icon="categoryIcon" :color="categoryColor" size="large" class="me-3" />
        <div class="flex-grow-1">
          <div class="text-h5 font-weight-bold">{{ hunt?.display_name }}</div>
          <div class="text-subtitle-1 text-medium-emphasis">{{ hunt?.category }} Hunt</div>
        </div>
        <v-btn
          icon="mdi-close"
          variant="text"
          @click="handleClose"
        />
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-4">
        <!-- Hunt Description -->
        <div class="mb-4">
          <div class="text-h6 mb-2">Description</div>
          <div class="text-body-1">{{ hunt?.description }}</div>
        </div>

        <!-- Hunt Metadata -->
        <div class="mb-4">
          <div class="text-h6 mb-3">Hunt Information</div>
          <v-row>
            <v-col cols="6">
              <div class="d-flex align-center mb-2">
                <v-icon icon="mdi-tag" size="small" class="me-2" />
                <span class="text-body-2">
                  <strong>Category:</strong> {{ hunt?.category }}
                </span>
              </div>
              <div class="d-flex align-center mb-2">
                <v-icon icon="mdi-clock-outline" size="small" class="me-2" />
                <span class="text-body-2">
                  <strong>Version:</strong> {{ hunt?.version }}
                </span>
              </div>
            </v-col>
            <v-col cols="6">
              <div class="d-flex align-center mb-2">
                <v-icon icon="mdi-play-box-multiple" size="small" class="me-2" />
                <span class="text-body-2">
                  <strong>Steps:</strong> {{ hunt?.step_count || 0 }}
                </span>
              </div>
              <div class="d-flex align-center mb-2">
                <v-icon :icon="hunt?.is_active ? 'mdi-check-circle' : 'mdi-alert-circle'" 
                       :color="hunt?.is_active ? 'success' : 'error'" 
                       size="small" class="me-2" />
                <span class="text-body-2">
                  <strong>Status:</strong> {{ hunt?.is_active ? 'Active' : 'Inactive' }}
                </span>
              </div>
            </v-col>
          </v-row>
        </div>

        <!-- Parameters -->
        <div v-if="hunt?.initial_parameters && Object.keys(hunt.initial_parameters).length > 0" class="mb-4">
          <div class="text-h6 mb-3">Required Parameters</div>
          <v-table density="compact">
            <thead>
              <tr>
                <th>Parameter</th>
                <th>Type</th>
                <th>Required</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(paramDef, paramName) in hunt.initial_parameters" :key="paramName">
                <td class="font-weight-medium">{{ formatParameterName(paramName) }}</td>
                <td>
                  <v-chip size="x-small" variant="outlined">
                    {{ paramDef.type || 'string' }}
                  </v-chip>
                </td>
                <td>
                  <v-chip 
                    :color="paramDef.required ? 'error' : 'success'" 
                    size="x-small"
                    variant="flat"
                  >
                    {{ paramDef.required ? 'Yes' : 'No' }}
                  </v-chip>
                </td>
                <td class="text-body-2">{{ paramDef.description || 'No description' }}</td>
              </tr>
            </tbody>
          </v-table>
        </div>

        <!-- Hunt Steps (if available) -->
        <div v-if="huntSteps && huntSteps.length > 0" class="mb-4">
          <div class="text-h6 mb-3">Hunt Workflow</div>
          <v-timeline density="compact" side="end">
            <v-timeline-item
              v-for="(step, index) in huntSteps"
              :key="step.step_id"
              :dot-color="getStepColor(index)"
              size="small"
            >
              <template #opposite>
                <span class="text-caption">Step {{ index + 1 }}</span>
              </template>
              <div>
                <div class="text-body-1 font-weight-medium">{{ step.display_name }}</div>
                <div class="text-body-2 text-medium-emphasis mb-1">{{ step.description }}</div>
                <div class="d-flex align-center">
                  <v-chip size="x-small" variant="outlined" class="me-2">
                    {{ step.plugin_name }}
                  </v-chip>
                  <span v-if="step.optional" class="text-caption">Optional</span>
                </div>
              </div>
            </v-timeline-item>
          </v-timeline>
        </div>

        <!-- Warning for inactive hunts -->
        <v-alert v-if="!hunt?.is_active" type="warning" variant="tonal">
          This hunt is currently inactive and cannot be executed.
        </v-alert>
      </v-card-text>

      <!-- Actions -->
      <v-card-actions class="pa-4 pt-0">
        <v-spacer />
        <v-btn
          variant="text"
          @click="handleClose"
        >
          Close
        </v-btn>
        <v-btn
          color="primary"
          variant="elevated"
          @click="handleExecute"
          :disabled="!hunt?.is_active"
        >
          <v-icon icon="mdi-play" start />
          Execute Hunt
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  hunt: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'execute', 'close'])

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

const categoryColor = computed(() => {
  const colorMap = {
    person: 'blue',
    domain: 'green',
    company: 'orange',
    ip: 'purple',
    phone: 'teal',
    email: 'red',
    general: 'grey'
  }
  return colorMap[props.hunt?.category] || colorMap.general
})

const huntSteps = computed(() => {
  if (!props.hunt?.definition_json?.steps) return []
  return props.hunt.definition_json.steps
})

// Methods
const formatParameterName = (paramName) => {
  return paramName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const getStepColor = (index) => {
  const colors = ['primary', 'secondary', 'success', 'info', 'warning', 'error']
  return colors[index % colors.length]
}

const handleExecute = () => {
  emit('execute', props.hunt)
  handleClose()
}

const handleClose = () => {
  emit('close')
}
</script>

<style scoped>
.v-table th {
  font-weight: 600 !important;
}
</style>