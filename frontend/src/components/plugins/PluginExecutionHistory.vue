<template>
  <v-card variant="outlined" class="mt-4">
    <v-card-title>Plugin execution history</v-card-title>
    <v-card-text>
      <v-alert v-if="historyError" type="error" role="alert">{{ historyError }}</v-alert>
      <v-btn :loading="loading" variant="text" @click="load(false)">Refresh history</v-btn>
      <p v-if="!loading && !items.length">No plugin executions for this case.</p>
      <v-list aria-label="Plugin execution history">
        <v-list-item
          v-for="item in items"
          :key="item.id"
          :title="item.plugin_name"
          :subtitle="`${item.status} · ${new Date(item.created_at).toLocaleString()}`"
          @click="open(item.id)"
        />
      </v-list>
      <v-btn v-if="nextCursor" :loading="loading" @click="load(true)">Load more executions</v-btn>
      <section v-if="selected" aria-label="Selected plugin execution">
        <p v-if="execution" role="status">{{ execution.plugin_name }} — {{ execution.status }}</p>
        <v-alert v-if="error || execution?.error" type="error" role="alert">
          {{ error || execution.error.message }}
        </v-alert>
        <v-btn v-if="execution" @click="showResults = true">View retained results</v-btn>
      </section>
    </v-card-text>
  </v-card>
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
import { downloadBlob } from '@/utils/download'
import { ref, watch, onScopeDispose } from 'vue'
import { pluginService } from '@/services/plugin'
import { usePluginExecution } from '@/composables/usePluginExecution'
import PluginResultsModal from './PluginResultsModal.vue'

function exportResults(data) {
  downloadBlob(
    { blob: new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }) },
    `${data.pluginName}_results.json`,
  )
}

const props = defineProps({
  caseId: { type: Number, required: true },
  executionId: { type: Number, default: null },
})
const items = ref([])
const nextCursor = ref(null)
const loading = ref(false)
const historyError = ref(null)
const selected = ref(null)
const showResults = ref(false)
const { execution, results, error, observe, stop } = usePluginExecution()
let controller
async function load(more = false) {
  controller?.abort()
  controller = new AbortController()
  const signal = controller.signal
  loading.value = true
  try {
    const page = await pluginService.getHistory(props.caseId, more ? nextCursor.value : 0, signal)
    if (signal.aborted) return
    items.value = more ? [...items.value, ...page.items] : page.items
    nextCursor.value = page.next_cursor
    historyError.value = null
  } catch (failure) {
    if (!signal.aborted) historyError.value = failure.response?.data?.detail || failure.message
  } finally {
    if (!signal.aborted) loading.value = false
  }
}
function open(id) {
  selected.value = id
  observe(id)
}
watch(
  () => props.caseId,
  () => {
    stop()
    selected.value = null
    showResults.value = false
    items.value = []
    nextCursor.value = null
    load()
  },
  { immediate: true },
)
watch(
  () => props.executionId,
  (id) => {
    if (id) {
      open(id)
      load()
    }
  },
)
onScopeDispose(() => controller?.abort())
</script>
