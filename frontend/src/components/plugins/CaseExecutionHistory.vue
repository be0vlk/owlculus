<template>
  <section aria-label="Case execution history" class="case-execution-history">
    <div class="d-flex flex-wrap ga-2 mb-4">
      <v-btn variant="outlined" @click="refresh">Refresh history</v-btn>
      <v-btn v-if="allowHunts" color="primary" :to="`/case/${caseId}/hunts`">Browse Hunts</v-btn>
    </div>
    <p v-if="pluginLoading" role="status">Loading plugin history…</p>
    <p v-if="allowHunts && huntLoading" role="status">Loading hunt history…</p>
    <v-alert v-if="pluginError" type="error" role="alert" class="mb-3">
      Plugin history could not be loaded: {{ pluginError }}
      Available history remains below.
      <v-btn variant="text" @click="retryPlugins">Retry plugin history</v-btn>
    </v-alert>
    <v-alert v-if="allowHunts && huntError" type="error" role="alert" class="mb-3">
      Hunt history could not be loaded: {{ huntError }}
      Available history remains below.
      <v-btn variant="text" @click="loadHunts">Retry hunt history</v-btn>
    </v-alert>
    <p v-if="!pluginLoading && !pluginError && !plugins.length">
      No plugin executions for this case.
    </p>
    <p v-if="allowHunts && !huntLoading && !huntError && !hunts.length">
      No hunt executions for this case.
    </p>
    <p v-if="historyRepositioned" role="status">
      History updated. Returned to page 1 to include newly loaded executions.
    </p>
    <v-table v-if="rows.length" density="comfortable" class="history-table">
      <template #default>
        <caption class="text-left text-body-small pa-2">
          Plugin and hunt executions
        </caption>
        <thead>
          <tr>
            <th scope="col">Type</th>
            <th scope="col">Execution</th>
            <th scope="col">Status</th>
            <th scope="col">Started</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in visibleRows" :key="row.key">
            <td>{{ row.type }}</td>
            <td class="execution-name">
              {{ row.name }} <span class="text-medium-emphasis">#{{ row.id }}</span>
            </td>
            <td>{{ row.status }}</td>
            <td>{{ formatDate(row.createdAt) }}</td>
            <td>
              <v-btn
                variant="text"
                :aria-label="`View ${row.type} ${row.name} execution #${row.id}`"
                @click="open(row)"
                >View execution</v-btn
              >
            </td>
          </tr>
        </tbody>
      </template>
    </v-table>
    <div v-if="rows.length" class="d-flex flex-wrap align-center ga-2 mt-3">
      <v-select
        v-model="pageSize"
        :items="[10, 25, 50, 100]"
        label="Executions per page"
        density="compact"
        hide-details
        class="page-size"
      />
      <v-pagination
        v-model="page"
        :length="pageCount"
        :total-visible="3"
        aria-label="Execution history pages"
      />
      <span role="status">{{ rows.length }} loaded executions</span>
    </div>
    <v-btn
      v-if="nextCursor != null"
      class="mt-3"
      :loading="pluginLoading"
      @click="loadPlugins(true)"
    >
      Load more plugin executions
    </v-btn>
    <PluginExecutionViewer
      v-if="selected"
      :key="`${caseId}:${selected.key}:${selectionVersion}`"
      :execution-id="selected.id"
    />
  </section>
</template>

<script setup>
import { computed, onScopeDispose, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { huntService } from '@/services/hunt'
import { usePluginHistory } from '@/composables/usePluginHistory'
import { formatDate } from '@/composables/dateUtils'
import { formatHuntExecutionTitle } from '@/utils/huntDisplayUtils'
import PluginExecutionViewer from './PluginExecutionViewer.vue'

const props = defineProps({
  caseId: { type: Number, required: true },
  allowHunts: { type: Boolean, default: false },
})
const router = useRouter()
const {
  items: plugins,
  nextCursor,
  loading: pluginLoading,
  error: pluginError,
  accessDenied,
  load: loadPlugins,
  retry: retryPlugins,
} = usePluginHistory(() => props.caseId)
const hunts = ref([])
const huntLoading = ref(false)
const huntError = ref(null)
const selected = ref(null)
const selectionVersion = ref(0)
watch(
  accessDenied,
  (denied) => {
    if (denied) selected.value = null
  },
  { flush: 'sync' },
)
const page = ref(1)
const pageSize = ref(25)
const historyRepositioned = ref(false)
let huntController

async function loadHunts() {
  if (!props.allowHunts || !props.caseId) return
  huntController?.abort()
  huntController = new AbortController()
  const signal = huntController.signal
  const owner = props.caseId
  const current = () => !signal.aborted && props.allowHunts && props.caseId === owner
  huntLoading.value = true
  huntError.value = null
  try {
    const records = await huntService.getCaseExecutions(owner, signal)
    if (current()) hunts.value = [...new Map(records.map((item) => [item.id, item])).values()]
  } catch (failure) {
    if (current()) {
      if ([401, 403, 404].includes(failure.response?.status)) hunts.value = []
      huntError.value = failure.response?.data?.detail || failure.message
    }
  } finally {
    if (current()) huntLoading.value = false
  }
}

const rows = computed(() =>
  [
    ...plugins.value.map((item) => ({
      key: `plugin:${item.id}`,
      kind: 'plugin',
      type: 'Plugin',
      id: item.id,
      name: item.plugin_name,
      status: item.dispatch_state === 'recovery_waiting' ? 'Recovery waiting' : item.status,
      createdAt: item.created_at,
    })),
    ...(props.allowHunts ? hunts.value : []).map((item) => ({
      key: `hunt:${item.id}`,
      kind: 'hunt',
      type: 'Hunt',
      id: item.id,
      name: formatHuntExecutionTitle(
        item.hunt_display_name || 'Hunt Execution',
        item.initial_parameters || {},
        item.hunt_category || 'general',
      ),
      status: item.status,
      createdAt: item.created_at,
    })),
  ].sort(
    (a, b) =>
      new Date(b.createdAt) - new Date(a.createdAt) || b.id - a.id || a.key.localeCompare(b.key),
  ),
)

function open(row) {
  if (row.kind === 'hunt') {
    if (!props.allowHunts) return
    selected.value = null
    router.push(`/case/${props.caseId}/hunts/execution/${row.id}`)
  } else {
    selected.value = row
    selectionVersion.value++
  }
}

const pageCount = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize.value)))
const visibleRows = computed(() =>
  rows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value),
)
// Source pages can interleave ahead of the current page. Restart traversal so
// newly loaded executions cannot be silently skipped behind the reader.
watch(rows, () => {
  if (page.value > 1) historyRepositioned.value = true
  page.value = 1
})
watch(page, (value) => {
  if (value !== 1) historyRepositioned.value = false
})
watch(pageSize, () => {
  historyRepositioned.value = false
  page.value = 1
})

function refresh() {
  return Promise.all([loadPlugins(), loadHunts()])
}

watch(
  () => props.caseId,
  () => {
    selected.value = null
    historyRepositioned.value = false
    page.value = 1
  },
  { flush: 'sync' },
)
watch(
  () => [props.caseId, props.allowHunts],
  () => {
    huntController?.abort()
    hunts.value = []
    huntError.value = null
    huntLoading.value = false
    loadHunts()
  },
  { immediate: true, flush: 'sync' },
)
onScopeDispose(() => huntController?.abort())
</script>

<style scoped>
.case-execution-history {
  min-width: 0;
  max-width: 100%;
}

.history-table {
  max-width: 100%;
}

.execution-name {
  overflow-wrap: anywhere;
  min-width: 12rem;
}

.page-size {
  flex: 0 1 12rem;
}
</style>
