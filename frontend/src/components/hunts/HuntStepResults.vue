<template>
  <div class="hunt-step-results">
    <!-- Step Information -->
    <div class="mb-4">
      <v-row>
        <v-col cols="12" md="6">
          <div class="text-caption font-weight-medium">Plugin</div>
          <div class="text-body-2">{{ step.plugin_name }}</div>
        </v-col>
        <v-col cols="12" md="6">
          <div class="text-caption font-weight-medium">Step ID</div>
          <div class="text-body-2">{{ step.step_id }}</div>
        </v-col>
      </v-row>
      
      <!-- Parameters -->
      <div v-if="step.parameters && Object.keys(step.parameters).length > 0" class="mt-3">
        <div class="text-caption font-weight-medium mb-2">Parameters</div>
        <v-chip
          v-for="(value, key) in step.parameters"
          :key="key"
          size="small"
          variant="outlined"
          class="mr-2 mb-1"
        >
          {{ key }}: {{ value }}
        </v-chip>
      </div>
      
      <!-- Error Details -->
      <div v-if="step.status === 'failed' && step.error_details" class="mt-3">
        <v-alert type="error" variant="tonal" density="compact">
          {{ step.error_details }}
        </v-alert>
      </div>
    </div>

    <v-divider class="mb-4" />

    <!-- Display results based on plugin type -->
    <div v-if="step.status === 'completed' && displayResults.length > 0">
      <div
        v-for="(result, index) in displayResults"
        :key="index"
        class="result-item mb-3"
      >
        <v-card variant="outlined" density="compact">
          <v-card-text class="pa-3">
            <!-- Generic result display -->
            <div v-if="typeof result === 'object'">
              <div v-for="(value, key) in result" :key="key" class="mb-1">
                <span class="text-caption font-weight-medium">{{ formatKey(key) }}:</span>
                <span class="text-caption ml-2">{{ formatValue(value) }}</span>
              </div>
            </div>
            <!-- Simple value display -->
            <div v-else class="text-body-2">
              {{ result }}
            </div>
          </v-card-text>
        </v-card>
      </div>
    </div>

    <!-- Empty state for completed steps -->
    <div v-else-if="step.status === 'completed'" class="text-center pa-4">
      <v-icon icon="mdi-information-outline" color="grey" class="mb-2" />
      <div class="text-caption text-medium-emphasis">No results to display</div>
    </div>
    
    <!-- Pending state -->
    <div v-else-if="step.status === 'pending'" class="text-center pa-4">
      <v-icon icon="mdi-clock-outline" color="grey" class="mb-2" />
      <div class="text-caption text-medium-emphasis">Step not yet executed</div>
    </div>
    
    <!-- Running state -->
    <div v-else-if="step.status === 'running'" class="text-center pa-4">
      <v-progress-circular indeterminate size="32" color="primary" />
      <div class="text-caption text-medium-emphasis mt-2">Step is currently running...</div>
    </div>
    
    <!-- Skipped state -->
    <div v-else-if="step.status === 'skipped'" class="text-center pa-4">
      <v-icon icon="mdi-skip-next" color="warning" class="mb-2" />
      <div class="text-caption text-medium-emphasis">Step was skipped</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  step: {
    type: Object,
    required: true
  },
  stepNumber: {
    type: Number,
    required: true
  }
})

// Computed properties
const displayResults = computed(() => {
  if (!props.step?.output) return []
  
  // Handle different output formats
  if (Array.isArray(props.step.output)) {
    return props.step.output
  } else if (props.step.output.results && Array.isArray(props.step.output.results)) {
    return props.step.output.results
  } else if (props.step.output.data && Array.isArray(props.step.output.data)) {
    return props.step.output.data
  } else if (typeof props.step.output === 'object') {
    return [props.step.output]
  }
  return []
})

// Methods
const formatKey = (key) => {
  return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const formatValue = (value) => {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'string' && value.length > 100) {
    return value.substring(0, 97) + '...'
  }
  return String(value)
}
</script>

<style scoped>
.result-item {
  transition: all 0.2s ease;
}

.result-item:hover {
  transform: translateY(-1px);
}
</style>