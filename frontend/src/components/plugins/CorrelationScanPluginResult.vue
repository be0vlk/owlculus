<template>
  <div class="d-flex flex-column ga-4">
    <div v-if="latestProgress">
      <p role="status" class="text-body-medium mb-2">{{ latestProgress.message }}</p>
      <v-progress-linear indeterminate rounded />
    </div>
    <p v-if="!retrievalComplete" class="text-body-medium">
      Partial retained results — counts reflect loaded matches.
    </p>
    <p v-if="executionStatus === 'cancelled'" role="status">
      Execution cancelled. Retained output may be partial.
    </p>

    <PluginStatusAlert
      v-for="error in errors"
      :key="error.data.message"
      type="error"
      plugin-name="Correlation Scan"
      :message="error.data.message"
    />
    <v-alert v-if="completionMessage" type="success" variant="tonal" density="compact">
      {{ completionMessage }}
    </v-alert>

    <v-alert v-if="notices.length" type="warning" variant="tonal">
      {{ notices.length }} malformed
      {{ notices.length === 1 ? 'reference was' : 'references were' }}
      skipped; reference coverage is incomplete.
      <details class="mt-2">
        <summary>Skipped references</summary>
        <ul class="pl-6">
          <li v-for="notice in notices" :key="noticeKey(notice)">
            <a
              v-if="notice.case_id != null && notice.entity_id != null"
              :href="entityHref(notice.case_id, notice.entity_id)"
              target="_blank"
              rel="noopener"
              >Entity #{{ notice.entity_id }} in Case #{{ notice.case_id }}</a
            >
            <span v-if="notice.field"> · {{ fieldLabel(notice.field) }}</span>
          </li>
        </ul>
      </details>
    </v-alert>

    <template v-if="rows.length">
      <div class="d-flex flex-column ga-2">
        <h3 class="text-title-large font-weight-medium mb-0">
          {{ counts.entities }} source Entities · {{ counts.matches }} matches ·
          {{ counts.cases }} related Cases
        </h3>
        <p class="text-body-medium text-medium-emphasis mb-0">
          Connections are investigative leads; they do not establish identity.
        </p>
        <div class="d-flex flex-wrap align-center ga-2">
          <v-chip-group v-model="selectedStrengths" filter multiple selected-class="text-primary">
            <v-chip
              v-for="option in STRENGTHS"
              :key="option.value"
              :value="option.value"
              variant="outlined"
              filter
            >
              {{ option.title }} ({{ strengthCounts[option.value] }})
            </v-chip>
          </v-chip-group>
          <v-text-field
            v-model="search"
            prepend-inner-icon="mdi-magnify"
            label="Search connections"
            single-line
            hide-details
            clearable
            density="compact"
            class="flex-grow-1"
            style="min-width: 12rem"
          />
        </div>
      </div>

      <v-data-table
        v-model:expanded="expanded"
        :headers="HEADERS"
        :items="filteredRows"
        :items-per-page="25"
        :items-per-page-options="[10, 25, 50, 100]"
        :group-by="[{ key: 'sourceEntityId' }]"
        :sort-by="[{ key: 'strength', order: 'asc' }]"
        no-data-text="No connections match the current filters."
        item-value="key"
        density="compact"
        class="elevation-1"
        rounded="lg"
        show-expand
        open-all
      >
        <template #group-header="{ item: group, columns, toggleGroup, isGroupOpen }">
          <tr class="v-data-table-group-header-row">
            <td :colspan="columns.length">
              <div class="d-flex align-center ga-2">
                <v-btn
                  :icon="isGroupOpen(group) ? 'mdi-chevron-down' : 'mdi-chevron-right'"
                  :aria-label="`${isGroupOpen(group) ? 'Collapse' : 'Expand'} ${groupSource(group).sourceLabel}`"
                  :aria-expanded="isGroupOpen(group)"
                  size="small"
                  variant="text"
                  @click="toggleGroup(group)"
                />
                <h3 class="text-title-medium font-weight-medium mb-0">
                  {{ groupSource(group).sourceLabel }}
                </h3>
                <v-chip size="small" variant="tonal" color="primary">
                  {{ groupSource(group).sourceType }}
                </v-chip>
                <span class="text-body-medium text-medium-emphasis">
                  {{ group.items.length }} {{ group.items.length === 1 ? 'match' : 'matches' }}
                </span>
                <v-btn
                  :href="
                    entityHref(groupSource(group).sourceCaseId, groupSource(group).sourceEntityId)
                  "
                  :aria-label="`Open source ${groupSource(group).sourceLabel}`"
                  target="_blank"
                  rel="noopener"
                  icon="mdi-open-in-new"
                  size="small"
                  variant="text"
                />
              </div>
            </td>
          </tr>
        </template>

        <template #[`item.matchType`]="{ item }">{{ getMatchTypeLabel(item.matchType) }}</template>

        <template #[`item.relatedLabel`]="{ item }">
          <div class="font-weight-medium">{{ item.relatedLabel }}</div>
          <div class="text-body-small text-medium-emphasis">{{ item.relatedType }}</div>
        </template>

        <template #[`item.caseNumber`]="{ item }">
          <div class="font-weight-medium">Case #{{ item.caseNumber ?? item.caseId }}</div>
          <div class="text-body-small text-medium-emphasis">{{ item.caseTitle }}</div>
        </template>

        <template #[`item.strength`]="{ item }">
          <v-chip
            :color="STRENGTHS[item.strength].color"
            :title="item.signal"
            size="small"
            variant="tonal"
          >
            {{ STRENGTHS[item.strength].title }}
          </v-chip>
        </template>

        <template #[`item.actions`]="{ item }">
          <v-btn
            :href="entityHref(item.caseId, item.entityId)"
            :aria-label="`Open ${item.relatedLabel} in Case #${item.caseNumber ?? item.caseId}`"
            target="_blank"
            rel="noopener"
            icon="mdi-open-in-new"
            size="small"
            variant="text"
          />
        </template>

        <template #expanded-row="{ columns, item }">
          <tr>
            <td :colspan="columns.length" class="py-3">
              <div class="d-flex flex-column ga-1 text-body-medium">
                <p v-for="field in item.sourceFields" class="mb-0" :key="field.field + field.value">
                  Source {{ fieldLabel(field.field) }}: {{ field.value }}
                </p>
                <p v-for="field in item.fields" class="mb-0" :key="field.field + field.value">
                  Related {{ fieldLabel(field.field) }}: {{ field.value }}
                </p>
                <p v-if="!item.fields.length && item.foundIn" class="mb-0">{{ item.foundIn }}</p>
                <p v-if="item.signal" class="mb-0">{{ item.signal }}</p>
              </div>
            </td>
          </tr>
        </template>
      </v-data-table>
    </template>

    <v-card
      v-if="normalizedResult.length === 0 && completedSuccessfully"
      elevation="1"
      rounded="lg"
    >
      <v-card-text class="text-center pa-8">
        <v-icon icon="mdi-magnify" size="48" color="grey-darken-1" class="mb-3" />
        <p class="text-body-medium text-medium-emphasis">
          No correlations are available in accessible Cases.
        </p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import PluginStatusAlert from './PluginStatusAlert.vue'
import { assembleCorrelationResults, correlationRows } from '@/utils/correlationResults'
import { formatParameterName } from '@/utils/huntDisplayUtils'

const props = defineProps({
  executionStatus: { type: String, default: null },
  executionPartial: { type: Boolean, default: false },
  retrievalComplete: { type: Boolean, default: true },
  result: {
    type: [Object, Array],
    required: true,
  },
})

const router = useRouter()

const STRENGTHS = [
  { value: 0, title: 'Exact identifier', color: 'primary' },
  { value: 1, title: 'Association', color: 'info' },
  { value: 2, title: 'Weak', color: 'grey' },
]
// Vuetify treats a titleless zero-width group column as empty, so rows get no spacer cell.
const HEADERS = [
  { key: 'data-table-group', title: '', width: 0 },
  { title: 'Match', key: 'matchType' },
  { title: 'Shared value', key: 'sharedValue' },
  { title: 'Related entity', key: 'relatedLabel' },
  { title: 'Case', key: 'caseNumber' },
  { title: 'Strength', key: 'strength' },
  { title: 'Open', key: 'actions', sortable: false, align: 'end' },
]

const selectedStrengths = ref([0, 1])
const search = ref('')
const expanded = ref([])

const normalizedResult = computed(() => assembleCorrelationResults(props.result))
const rows = computed(() => correlationRows(normalizedResult.value))

const unique = (items, keyOf) => [...new Map(items.map((item) => [keyOf(item), item])).values()]
const errors = computed(() =>
  unique(
    normalizedResult.value.filter((item) => item.type === 'error'),
    (item) => item.data?.message,
  ),
)
const noticeKey = (notice) =>
  [notice.case_id, notice.entity_id, notice.field, notice.message].join(':')
const notices = computed(() =>
  unique(
    normalizedResult.value
      .map((item) => item.data)
      .filter((data) => data?.notice_type === 'skipped_reference'),
    noticeKey,
  ),
)

const hasCorrelations = computed(() => rows.value.length > 0)
const completedSuccessfully = computed(
  () =>
    props.retrievalComplete &&
    !props.executionPartial &&
    !errors.value.length &&
    (!props.executionStatus || props.executionStatus === 'completed'),
)
const completionMessage = computed(() => {
  if (!completedSuccessfully.value || !normalizedResult.value.some((i) => i.type === 'complete'))
    return ''
  if (notices.value.length)
    return 'Correlation scan completed with skipped references; reference coverage is incomplete.'
  return hasCorrelations.value
    ? 'Correlation scan complete'
    : 'Correlation scan complete. No correlations are available in accessible Cases.'
})

const latestProgress = computed(() => {
  if (['completed', 'failed', 'cancelled'].includes(props.executionStatus)) return null
  if (normalizedResult.value.some((item) => ['complete', 'error'].includes(item.type))) return null
  return normalizedResult.value.findLast((item) => item.type === 'status')?.data || null
})

const counts = computed(() => ({
  entities: new Set(rows.value.map((row) => row.sourceEntityId)).size,
  matches: rows.value.length,
  cases: new Set(rows.value.map((row) => row.caseId)).size,
}))
const strengthCounts = computed(() =>
  STRENGTHS.map((option) => rows.value.filter((row) => row.strength === option.value).length),
)

const searchText = (row) =>
  [
    getMatchTypeLabel(row.matchType),
    row.sourceLabel,
    row.sourceType,
    row.sharedValue,
    row.relatedLabel,
    row.relatedType,
    row.caseNumber,
    row.caseTitle,
    row.foundIn,
    row.signal,
    ...[...row.sourceFields, ...row.fields].map((field) => field.value),
  ]
    .join('\n')
    .toLowerCase()
const filteredRows = computed(() => {
  const query = (search.value || '').trim().toLowerCase()
  return rows.value.filter(
    (row) =>
      selectedStrengths.value.includes(row.strength) && (!query || searchText(row).includes(query)),
  )
})

const groupSource = (group) => group.items[0].raw

const entityHref = (caseId, entityId) =>
  router.resolve({ name: 'CaseDetails', params: { id: caseId }, query: { entity: entityId } }).href

const fieldLabel = (field) => formatParameterName(field.replace(/\[\d+\]/g, '').replace(/\./g, ' '))

const getMatchTypeLabel = (matchType) => {
  const labels = {
    name: 'Name Match',
    employer: 'Employer Match',
    domain: 'Domain Match',
    vin: 'VIN Match',
    email: 'Email Match',
    phone: 'Phone Match',
    ip_address: 'IP Address Match',
    exact_profile: 'Exact Profile Reference',
    license_plate: 'License Plate Match',
  }
  return labels[matchType] || 'Match'
}
</script>
