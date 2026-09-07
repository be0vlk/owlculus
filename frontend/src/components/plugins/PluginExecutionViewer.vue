<template>
  <section aria-label="Selected plugin execution" class="mt-4">
    <p v-if="execution" role="status">{{ execution.plugin_name }} — {{ execution.status }}</p>
    <ExecutionWaiting :execution="execution" />
    <v-btn
      v-if="['queued', 'running'].includes(execution?.status)"
      :loading="cancelling"
      color="error"
      @click="cancel"
      >Cancel execution</v-btn
    >
    <v-alert v-if="error || execution?.error" type="error" role="alert">
      {{ error || execution.error.message }}
    </v-alert>
    <v-btn v-if="execution" @click="showResults = true">View retained results</v-btn>
  </section>
  <PluginResultsModal
    v-if="execution"
    v-model="showResults"
    :plugin-name="execution.plugin_name"
    :results="results"
    :parameters="execution.parameters"
    :error="execution.error?.message"
    :execution-time="new Date(execution.created_at)"
    @export="exportResults"
  />
</template>

<script setup>
import { ref, watch } from 'vue'
import ExecutionWaiting from '@/components/ExecutionWaiting.vue'
import { downloadBlob } from '@/utils/download'
import { usePluginExecution } from '@/composables/usePluginExecution'
import PluginResultsModal from './PluginResultsModal.vue'

const props = defineProps({ executionId: { type: Number, required: true } })
const showResults = ref(false)
const { execution, results, error, observe, cancel, cancelling } = usePluginExecution()
watch(
  () => props.executionId,
  (id) => {
    showResults.value = false
    observe(id)
  },
  { immediate: true },
)

function exportResults(data) {
  downloadBlob(
    { blob: new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }) },
    `${data.pluginName}_results.json`,
  )
}
</script>
