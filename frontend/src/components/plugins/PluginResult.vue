<template>
  <div class="plugin-result">
    <v-alert v-if="executionError" type="error" role="alert" class="mb-4">
      Plugin execution failed. {{ executionError }}
    </v-alert>
    <p v-else-if="executionStatus === 'failed'" role="status">Plugin execution failed.</p>
    <p v-if="executionPartial" role="status">Partial retained output.</p>
    <p v-if="retrievalLoading" role="status">Loading retained results…</p>
    <v-alert v-if="retrievalError" type="warning" role="alert" class="mb-4">
      Partial retained results. {{ retrievalError }}
      <v-btn variant="text" @click="$emit('retry')">Retry retrieval</v-btn>
    </v-alert>
    <v-alert v-if="exportError" type="error" role="alert" class="mb-4">{{ exportError }}</v-alert>
    <p v-if="['queued', 'running', 'cancelling'].includes(executionStatus)" role="status">
      Execution {{ executionStatus }}. Retained output may be partial.
    </p>
    <component
      :is="pluginComponent"
      v-if="pluginComponent"
      :result="result"
      :execution-status="executionStatus"
      :execution-partial="executionPartial"
      :retrieval-complete="retrievalComplete"
    />
    <div v-else class="fallback-result">
      <!-- Fallback for plugins without custom components -->
      <v-card v-for="(item, index) in result" :key="index" class="mb-2" elevation="1" rounded="lg">
        <v-card-text>
          <pre class="text-body-medium font-mono">{{ formatValue(item) }}</pre>
        </v-card-text>
      </v-card>
    </div>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent } from 'vue'

const props = defineProps({
  executionStatus: { type: String, default: null },
  executionPartial: { type: Boolean, default: false },
  executionError: { type: String, default: null },
  retrievalLoading: { type: Boolean, default: false },
  retrievalComplete: { type: Boolean, default: true },
  retrievalError: { type: String, default: null },
  exportError: { type: String, default: null },
  result: { type: Array, required: true },
  pluginName: { type: String, required: true },
})

defineEmits(['retry'])

const pluginModules = import.meta.glob('./*PluginResult.vue')

const pluginComponent = computed(() => {
  const name = props.pluginName.replace(/Plugin$/, '').replace(/^[a-z]/, (c) => c.toUpperCase())
  const loader = pluginModules[`./${name}PluginResult.vue`]
  return loader && defineAsyncComponent(loader)
})

const formatValue = (value) => {
  if (value === null) return 'Not available'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}
</script>

<style scoped>
.plugin-result {
  width: 100%;
}

.fallback-result pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.fallback-result {
  width: 100%;
}
</style>
