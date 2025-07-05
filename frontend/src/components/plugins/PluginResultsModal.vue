<template>
  <v-dialog
    v-model="isOpen"
    :fullscreen="mdAndDown"
    :max-width="!mdAndDown ? '90vw' : undefined"
    persistent
    scrollable
  >
    <v-card height="90vh" class="d-flex flex-column">
      <!-- Header -->
      <v-card-title class="d-flex align-center ga-3 px-6 py-4">
        <v-icon :icon="getPluginIcon(pluginName)" size="24" />
        <div class="flex-grow-1">
          <h2 class="text-h5 font-weight-medium">{{ getPluginDisplayName(pluginName) }} Results</h2>
          <div class="text-body-2 text-medium-emphasis">
            Executed {{ formatExecutionTime(executionTime) }}
          </div>
        </div>

        <!-- Action buttons -->
        <div class="d-flex ga-2">
          <v-btn
            v-if="results"
            variant="tonal"
            color="primary"
            prepend-icon="mdi-download"
            @click="exportResults"
          >
            Export
          </v-btn>
          <v-btn icon="mdi-close" variant="text" @click="closeModal" />
        </div>
      </v-card-title>

      <v-divider />

      <!-- Content -->
      <v-card-text class="flex-grow-1 pa-0">
        <v-container class="py-6 px-6" style="max-width: none">
          <!-- Plugin Parameters Display -->
          <v-card
            v-if="parameters && Object.keys(parameters).length"
            variant="outlined"
            class="mb-6"
          >
            <v-card-title class="text-subtitle-1 py-3">
              <v-icon icon="mdi-cog" class="mr-2" size="20" />
              Execution Parameters
            </v-card-title>
            <v-divider />
            <v-card-text class="py-3">
              <div class="d-flex flex-wrap ga-3">
                <v-chip
                  v-for="(value, key) in parameters"
                  :key="key"
                  variant="tonal"
                  color="primary"
                  size="small"
                >
                  <strong>{{ formatParameterName(key) }}:</strong>
                  <span class="ml-1">{{ formatParameterValue(value) }}</span>
                </v-chip>
              </div>
            </v-card-text>
          </v-card>

          <!-- Results Display -->
          <div v-if="results" class="results-container">
            <PluginResult :plugin-name="pluginName" :result="results" class="modal-plugin-result" />
          </div>

          <!-- Error Display -->
          <v-alert v-else-if="error" class="ma-0" prominent type="error" variant="tonal">
            <template #title>
              <div class="d-flex align-center">
                <v-icon icon="mdi-alert-circle" class="mr-2" />
                Plugin Execution Failed
              </div>
            </template>
            <div class="text-body-1">{{ error }}</div>
          </v-alert>

          <!-- No Results State -->
          <v-card v-else variant="outlined" class="text-center pa-8">
            <v-icon class="mb-4" color="grey-darken-1" icon="mdi-file-search-outline" size="64" />
            <h3 class="text-h6 mb-2">No Results Available</h3>
            <p class="text-body-2 text-medium-emphasis">
              Plugin execution did not produce any results.
            </p>
          </v-card>
        </v-container>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { useDisplay } from 'vuetify'
import PluginResult from '@/components/plugins/PluginResult.vue'
import { formatDate } from '@/composables/dateUtils.js'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  pluginName: {
    type: String,
    required: true,
  },
  results: {
    type: [Object, Array, String, Number, Boolean],
    default: null,
  },
  error: {
    type: String,
    default: null,
  },
  parameters: {
    type: Object,
    default: () => ({}),
  },
  executionTime: {
    type: Date,
    default: () => new Date(),
  },
})

const emit = defineEmits(['update:modelValue', 'export'])

const { mdAndDown } = useDisplay()

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const closeModal = () => {
  isOpen.value = false
}

const getPluginDisplayName = (name) => {
  if (!name) return 'Unknown Plugin'

  // Remove 'Plugin' suffix and capitalize
  return name
    .replace(/Plugin$/, '')
    .replace(/([A-Z])/g, ' $1')
    .trim()
    .replace(/^./, (str) => str.toUpperCase())
}

const getPluginIcon = (name) => {
  const iconMap = {
    holehe: 'mdi-account-search',
    dnslookup: 'mdi-dns',
    correlation: 'mdi-chart-scatter-plot',
    default: 'mdi-puzzle',
  }

  const pluginKey = name?.toLowerCase().replace('plugin', '') || 'default'
  return iconMap[pluginKey] || iconMap.default
}

const formatExecutionTime = (time) => {
  if (!time) return 'Unknown time'
  return formatDate(time.toISOString())
}

const formatParameterName = (key) => {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

const formatParameterValue = (value) => {
  if (value === null || value === undefined) return 'Not set'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const exportResults = () => {
  emit('export', {
    pluginName: props.pluginName,
    results: props.results,
    parameters: props.parameters,
    executionTime: props.executionTime,
  })
}
</script>

<style scoped>
.results-container {
  width: 100%;
}

/* Enhanced styles for modal plugin results */
:deep(.modal-plugin-result) {
  /* Remove any width restrictions from the modal context */
  width: 100%;
  max-width: none;
}

/* Better spacing for cards in modal */
:deep(.modal-plugin-result .v-card) {
  margin-bottom: 1rem;
}

/* Improved table layouts for DNS and other data */
:deep(.modal-plugin-result .v-card-text) {
  padding: 1rem;
}

/* Better pre/code formatting in wide layout */
:deep(.modal-plugin-result pre) {
  white-space: pre-wrap;
  overflow-wrap: break-word;
  max-width: 100%;
  overflow-x: auto;
}
</style>
