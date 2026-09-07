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
          :subtitle="`${item.dispatch_state === 'recovery_waiting' ? 'Recovery waiting' : item.status} · ${new Date(item.created_at).toLocaleString()}`"
          @click="open(item.id)"
        />
      </v-list>
      <v-btn v-if="nextCursor" :loading="loading" @click="load(true)">Load more executions</v-btn>
      <PluginExecutionViewer
        v-if="selected"
        :key="`${caseId}:${selected}:${selectionVersion}`"
        :execution-id="selected"
      />
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, watch } from 'vue'
import { usePluginHistory } from '@/composables/usePluginHistory'
import PluginExecutionViewer from './PluginExecutionViewer.vue'

const props = defineProps({
  caseId: { type: Number, required: true },
  executionId: { type: Number, default: null },
})
const {
  items,
  nextCursor,
  loading,
  error: historyError,
  accessDenied,
  load,
} = usePluginHistory(() => props.caseId)
const selected = ref(null)
watch(
  accessDenied,
  (denied) => {
    if (denied) selected.value = null
  },
  { flush: 'sync' },
)
const selectionVersion = ref(0)
function open(id) {
  selected.value = id
  selectionVersion.value++
}
watch(
  () => props.caseId,
  () => {
    selected.value = null
  },
  { flush: 'sync' },
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
</script>
