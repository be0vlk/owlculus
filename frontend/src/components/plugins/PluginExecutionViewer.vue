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
    <v-btn v-if="execution" @click="reopenResults">View retained results</v-btn>
  </section>
  <PluginResultsModal
    v-if="execution"
    v-model="showResults"
    :plugin-name="execution.plugin_name"
    :results="results"
    :parameters="execution.parameters"
    :execution-status="execution.status"
    :retrieval-loading="retrievalLoading"
    :retrieval-complete="retrievalComplete"
    :retrieval-error="error"
    :export-error="exportError"
    @retry="retry"
    :error="execution.error?.message"
    :execution-time="new Date(execution.created_at)"
    @export="exportResults"
  />
</template>

<script setup>
import { ref, watch, onScopeDispose } from 'vue'
import { assembleCorrelationResults } from '@/utils/correlationResults'
import ExecutionWaiting from '@/components/ExecutionWaiting.vue'
import { pluginService } from '@/services/plugin'
import { downloadBlob } from '@/utils/download'
import { usePluginExecution } from '@/composables/usePluginExecution'
import PluginResultsModal from './PluginResultsModal.vue'

const props = defineProps({ executionId: { type: Number, required: true } })
const showResults = ref(false)
const exportError = ref(null)
let selection = 0
onScopeDispose(() => selection++)
const {
  clearInaccessibleContent,
  execution,
  results,
  error,
  retrievalLoading,
  retrievalComplete,
  retry,
  observe,
  cancel,
  cancelling,
} = usePluginExecution()
watch(
  () => props.executionId,
  (id) => {
    selection++
    exportError.value = null
    showResults.value = false
    observe(id)
  },
  { immediate: true },
)

function reopenResults() {
  selection++
  exportError.value = null
  observe(props.executionId)
  showResults.value = true
}

async function exportResults(data) {
  const id = props.executionId
  const current = selection
  exportError.value = null
  try {
    const state = await pluginService.getExecution(id)
    const visible = []
    let cursor = 0
    do {
      if (current !== selection) return
      const page = await pluginService.getResults(id, cursor)
      if (current !== selection) return
      visible.push(...page.items)
      cursor = page.next_cursor
    } while (cursor != null)
    if (current !== selection) return
    data = {
      ...data,
      results:
        state.plugin_name === 'CorrelationScan' ? assembleCorrelationResults(visible) : visible,
      parameters: state.parameters,
      partial: state.status !== 'completed',
      error: state.error?.message || null,
    }
    downloadBlob(
      { blob: new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }) },
      `${data.pluginName}_results.json`,
    )
  } catch (failure) {
    if (current !== selection) return
    if ([401, 403, 404].includes(failure.response?.status)) {
      clearInaccessibleContent()
    }
    exportError.value =
      'Could not export current results. Retry export or reopen the execution to check access.'
  }
}
</script>
