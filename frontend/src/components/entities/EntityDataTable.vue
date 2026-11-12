<template>
  <div>
    <v-row class="mb-4" no-gutters>
      <v-col cols="12">
        <v-chip-group v-model="selectedTypes" filter multiple selected-class="text-primary">
          <v-chip
            v-for="type in ENTITY_TYPES"
            :key="type.value"
            :value="type.value"
            variant="outlined"
            filter
          >
            <v-icon start size="small">{{ type.icon }}</v-icon>
            {{ type.title }}
          </v-chip>
        </v-chip-group>
      </v-col>
    </v-row>

    <v-alert
      v-if="loadErrorMessage"
      data-testid="entity-load-error"
      class="mb-4"
      type="error"
      variant="tonal"
    >
      {{ loadErrorMessage }}
      <v-btn
        data-testid="retry-entity-load"
        class="ml-2"
        size="small"
        variant="text"
        @click="loadItems"
      >
        Retry
      </v-btn>
    </v-alert>

    <v-data-table
      v-if="!loadErrorMessage"
      v-model="selected"
      :headers="HEADERS"
      :items="filteredEntities"
      :items-per-page="25"
      :items-per-page-options="ITEMS_PER_PAGE_OPTIONS"
      :loading="loading"
      :search="search"
      :custom-filter="matchesSearch"
      density="compact"
      item-value="id"
      class="elevation-1"
      rounded="lg"
      hover
      show-select
      return-object
      @click:row="(event, { item }) => emit('view', item, event)"
    >
      <template v-slot:top>
        <div class="entity-table-toolbar d-flex flex-wrap align-center ga-2 pa-2">
          <v-text-field
            v-model="search"
            data-testid="entity-search"
            prepend-inner-icon="mdi-magnify"
            label="Search entities"
            single-line
            hide-details
            clearable
            density="compact"
            class="entity-search flex-grow-1"
          />

          <v-btn
            v-if="selected.length > 0"
            color="error"
            variant="outlined"
            size="small"
            prepend-icon="mdi-delete"
            :disabled="deleting"
            @click="deleteEntities(selected, `${selected.length} entities`)"
            class="mr-2"
          >
            Delete ({{ selected.length }})
          </v-btn>

          <v-menu>
            <template #activator="{ props: menuProps }">
              <v-btn
                v-bind="menuProps"
                data-testid="entity-export-button"
                variant="outlined"
                size="small"
                prepend-icon="mdi-download"
                :disabled="filteredEntities.length === 0 || exporting"
                :loading="exporting"
              >
                Export
              </v-btn>
            </template>
            <v-list density="compact">
              <v-list-item
                data-testid="export-csv"
                prepend-icon="mdi-file-delimited"
                title="Export as CSV"
                @click="exportEntities('csv')"
              />
              <v-list-item
                data-testid="export-json"
                prepend-icon="mdi-code-json"
                title="Export as JSON"
                @click="exportEntities('json')"
              />
            </v-list>
          </v-menu>
        </div>
      </template>

      <template #[`item.entity_type`]="{ item }">
        <v-chip :color="entityType(item.entity_type)?.color || 'grey'" size="small" variant="flat">
          <v-icon start size="small">{{ entityType(item.entity_type)?.icon || 'mdi-help' }}</v-icon>
          {{ entityType(item.entity_type)?.title || item.entity_type }}
        </v-chip>
      </template>

      <template #[`item.name`]="{ item }">
        <div class="d-flex align-center">
          <div>
            <div class="font-weight-medium">{{ getEntityName(item) }}</div>
            <div v-if="getEntitySubtitle(item)" class="text-body-small text-medium-emphasis">
              {{ getEntitySubtitle(item) }}
            </div>
          </div>
        </div>
      </template>

      <template #[`item.description`]="{ item }">
        <span class="text-body-medium">
          {{ item.data.description || '' }}
        </span>
      </template>

      <template #[`item.created_at`]="{ item }">
        <span class="text-body-medium">
          {{ formatDate(item.created_at) }}
        </span>
      </template>

      <template #[`item.actions`]="{ item }">
        <v-btn
          :aria-label="`View ${getEntityName(item)}`"
          :data-entity-view-id="item.id"
          icon="mdi-eye"
          size="small"
          variant="text"
          @click.stop="$emit('view', item, $event)"
        />
        <v-btn
          :aria-label="`Delete ${getEntityName(item)}`"
          icon="mdi-delete"
          :disabled="deleting"
          size="small"
          variant="text"
          color="error"
          @click.stop="deleteEntities([item], 'this entity')"
        />
      </template>

      <template v-slot:no-data>
        <v-container class="text-center pa-8">
          <v-icon class="mb-4" color="grey-lighten-1" size="64"> mdi-account-group-outline </v-icon>
          <h3 class="text-title-large font-weight-medium mb-2">No Entities Found</h3>
          <p class="text-body-medium text-medium-emphasis">
            {{ getNoDataMessage() }}
          </p>
          <v-btn
            class="mt-4"
            color="primary"
            prepend-icon="mdi-plus"
            @click="$emit('create', $event)"
          >
            Add First Entity
          </v-btn>
        </v-container>
      </template>

      <template v-slot:loading>
        <v-skeleton-loader v-for="i in 25" :key="i" class="border-b" type="table-row" />
      </template>
    </v-data-table>

    <ConfirmationDialog ref="confirmDialog" />

    <v-snackbar
      v-model="showError"
      data-testid="entity-action-error"
      color="error"
      role="alert"
      :timeout="6000"
    >
      {{ errorMessage }}
      <template #actions>
        <v-btn variant="text" @click="showError = false">Close</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { getEntityDisplayName } from '@/composables/entityDisplay'
import { ENTITY_TYPES, entityType } from '@/composables/entityTypes'
import { computed, onMounted, ref, watch } from 'vue'
import { formatDate } from '@/composables/dateUtils'
import { entityService } from '@/services/entity'
import { downloadBlob } from '@/utils/download'
import { getErrorMessage } from '@/utils/errorMessage'
import ConfirmationDialog from '../ConfirmationDialog.vue'

const props = defineProps({
  caseId: {
    type: Number,
    required: true,
  },
})

const emit = defineEmits(['view', 'create', 'deleted'])

const entities = ref([])
const loading = ref(false)
const search = ref('')
const loadErrorMessage = ref('')
const selectedTypes = ref([])
const selected = ref([])
const confirmDialog = ref(null)
const deleting = ref(false)
const exporting = ref(false)
const showError = ref(false)
const errorMessage = ref('')

const ITEMS_PER_PAGE_OPTIONS = [
  { value: 10, title: '10' },
  { value: 25, title: '25' },
  { value: 50, title: '50' },
  { value: 100, title: '100' },
]

// Zero-pad IPv4 octets so addresses sort numerically.
const sortableName = (entity) => {
  const name = getEntityDisplayName(entity).toLowerCase()
  return entity.entity_type === 'ip_address'
    ? name
        .split('.')
        .map((part) => part.padStart(3, '0'))
        .join('.')
    : name
}

const HEADERS = [
  { title: 'Type', key: 'entity_type', sortable: true },
  { title: 'Name', key: 'name', value: sortableName, sortable: true },
  { title: 'Description', key: 'description', sortable: false },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, align: 'end' },
]

const filteredEntities = computed(() =>
  selectedTypes.value.length
    ? entities.value.filter((entity) => selectedTypes.value.includes(entity.entity_type))
    : entities.value,
)

const matchesSearch = (_value, query, item) =>
  [getEntityDisplayName(item.raw), item.raw.data.description || ''].some((text) =>
    text.toLowerCase().includes(query.toLowerCase()),
  )

watch([selectedTypes, search], () => {
  selected.value = []
})

const loadItems = async () => {
  loading.value = true
  loadErrorMessage.value = ''

  try {
    const response = (await entityService.getCaseEntities(props.caseId)) || []
    entities.value = response.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } catch (error) {
    console.error('Error loading entities:', error)
    entities.value = []
    loadErrorMessage.value = getErrorMessage(error, 'Failed to load entities')
  } finally {
    loading.value = false
  }
}

const getEntityName = getEntityDisplayName

const getEntitySubtitle = (entity) => {
  switch (entity.entity_type) {
    case 'person':
      return entity.data.email
    case 'company':
      return entity.data.website
    case 'domain': {
      const subdomainCount = entity.data.subdomains?.length || 0
      return subdomainCount > 0 ? `${subdomainCount} subdomains` : null
    }
    default:
      return null
  }
}

const getNoDataMessage = () => {
  if (search.value) {
    return `No entities found matching "${search.value}"`
  }
  if (selectedTypes.value.length > 0) {
    return 'No entities found for the selected types'
  }
  return 'No entities have been added to this case yet'
}

const deleteEntities = async (targets, label) => {
  if (deleting.value) return
  try {
    await confirmDialog.value.confirmDelete(label)
  } catch {
    return
  }
  deleting.value = true
  showError.value = false
  const results = await Promise.allSettled(
    targets.map((item) => entityService.deleteEntity(props.caseId, item.id)),
  )
  const deletedItems = targets.filter((_, index) => results[index].status === 'fulfilled')
  const failedItems = targets.filter((_, index) => results[index].status === 'rejected')

  if (deletedItems.length > 0) emit('deleted', deletedItems)

  // Failed items stay selected so the user can retry them.
  selected.value = selected.value.filter((item) => failedItems.some(({ id }) => id === item.id))
  await loadItems()
  deleting.value = false

  if (failedItems.length > 0) {
    const firstFailure = results.find((result) => result.status === 'rejected')
    console.error('Error deleting entities:', firstFailure.reason)
    errorMessage.value = `${failedItems.length} ${failedItems.length === 1 ? 'entity' : 'entities'} could not be deleted: ${getErrorMessage(firstFailure.reason, 'deletion service unavailable')}`
    showError.value = true
  }
}

const exportEntities = async (format) => {
  if (filteredEntities.value.length === 0 || exporting.value) return

  exporting.value = true
  try {
    const download = await entityService.exportEntities(props.caseId, {
      format,
      entityTypes: selectedTypes.value,
      search: search.value,
    })
    const date = new Date().toISOString().split('T')[0]
    downloadBlob(download, `case-${props.caseId}-entities-${date}.${format}`)
  } catch (error) {
    console.error('Error exporting entities:', error)
    errorMessage.value = getErrorMessage(error, 'Failed to export entities')
    showError.value = true
  } finally {
    exporting.value = false
  }
}

defineExpose({
  refresh: loadItems,
})

onMounted(loadItems)
</script>

<style scoped>
.entity-search {
  min-width: min(100%, 16rem);
  max-width: 18.75rem;
}
</style>
