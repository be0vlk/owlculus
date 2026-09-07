<template>
  <div>
    <!-- Quick Filters -->
    <v-row class="mb-4" no-gutters>
      <v-col cols="12">
        <v-chip-group v-model="selectedTypes" filter multiple selected-class="text-primary">
          <v-chip
            v-for="type in entityTypes"
            :key="type.value"
            :value="type.value"
            variant="outlined"
            filter
          >
            <v-icon start size="small">{{ type.icon }}</v-icon>
            {{ type.text }}
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

    <!-- Data Table -->
    <v-data-table-server
      v-if="!loadErrorMessage"
      v-model:items-per-page="itemsPerPage"
      v-model:page="page"
      v-model:sort-by="sortBy"
      v-model="selected"
      :headers="headers"
      :items="entities"
      :items-length="totalItems"
      :loading="loading"
      :search="search"
      density="compact"
      item-value="id"
      class="elevation-1"
      rounded="lg"
      :items-per-page-options="itemsPerPageOptions"
      :hover="true"
      show-select
      return-object
      @update:options="loadItems"
    >
      <!-- Toolbar -->
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

          <!-- Bulk Actions -->
          <v-btn
            v-if="selected.length > 0"
            color="error"
            variant="outlined"
            size="small"
            prepend-icon="mdi-delete"
            @click="confirmBulkDelete"
            class="mr-2"
          >
            Delete ({{ selected.length }})
          </v-btn>

          <!-- Export Button -->
          <v-menu>
            <template #activator="{ props: menuProps }">
              <v-btn
                v-bind="menuProps"
                data-testid="entity-export-button"
                variant="outlined"
                size="small"
                prepend-icon="mdi-download"
                :disabled="totalItems === 0 || exporting"
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

      <!-- Type Column -->
      <template #[`item.entity_type`]="{ item }">
        <v-chip :color="getTypeColor(item.entity_type)" size="small" variant="flat">
          <v-icon start size="small">{{ getTypeIcon(item.entity_type) }}</v-icon>
          {{ getTypeLabel(item.entity_type) }}
        </v-chip>
      </template>

      <!-- Name Column -->
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

      <!-- Description Column -->
      <template #[`item.description`]="{ item }">
        <span class="text-body-medium">
          {{ item.data.description || '' }}
        </span>
      </template>

      <!-- Created Date Column -->
      <template #[`item.created_at`]="{ item }">
        <span class="text-body-medium">
          {{ formatDate(item.created_at) }}
        </span>
      </template>

      <!-- Actions Column -->
      <template #[`item.actions`]="{ item }">
        <v-btn
          :aria-label="`View ${getEntityName(item)}`"
          :data-entity-view-id="item.id"
          icon="mdi-eye"
          size="small"
          variant="text"
          @click="$emit('view', item, $event)"
        />
        <v-btn
          :aria-label="`Delete ${getEntityName(item)}`"
          icon="mdi-delete"
          size="small"
          variant="text"
          color="error"
          @click="confirmDelete(item)"
        />
      </template>

      <!-- No Data -->
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

      <!-- Loading -->
      <template v-slot:loading>
        <v-skeleton-loader v-for="i in itemsPerPage" :key="i" class="border-b" type="table-row" />
      </template>
    </v-data-table-server>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" aria-label="Confirm Delete" max-width="500">
      <v-card>
        <v-card-title id="delete-entities-dialog-title">
          <v-icon start color="error">mdi-alert</v-icon>
          Confirm Delete
        </v-card-title>
        <v-card-text>
          <span v-if="itemsToDelete.length === 1">
            Are you sure you want to delete this entity?
          </span>
          <span v-else> Are you sure you want to delete {{ itemsToDelete.length }} entities? </span>
          This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="cancelDelete"> Cancel </v-btn>
          <v-btn :loading="deleting" color="error" variant="flat" @click="performDelete">
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar
      v-model="showDeleteError"
      data-testid="entity-delete-error"
      color="error"
      role="alert"
      :timeout="6000"
    >
      {{ deleteErrorMessage }}
      <template #actions>
        <v-btn variant="text" @click="showDeleteError = false">Close</v-btn>
      </template>
    </v-snackbar>

    <v-snackbar
      v-model="showExportError"
      data-testid="entity-export-error"
      color="error"
      role="alert"
      :timeout="6000"
    >
      {{ exportErrorMessage }}
      <template #actions>
        <v-btn variant="text" @click="showExportError = false">Close</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { getEntityDisplayName } from '@/composables/useEntityDisplay'
import { computed, onMounted, ref, watch } from 'vue'
import { formatDate } from '@/composables/dateUtils'
import { downloadBlob } from '@/utils/download'
import { getErrorMessage } from '@/utils/errorMessage'
import { useDialogFocusRestore } from '@/composables/useDialogFocusRestore'

const props = defineProps({
  caseId: {
    type: Number,
    required: true,
  },
  entityService: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['view', 'create', 'deleted'])

// Data table state
const entities = ref([])
const loading = ref(false)
const totalItems = ref(0)
const page = ref(1)
const itemsPerPage = ref(25)
const sortBy = ref([])
const search = ref('')
const loadErrorMessage = ref('')

// Filter state
const selectedTypes = ref([])

// Selection state
const selected = ref([])

// Dialog state
const deleteDialog = ref(false)
const itemsToDelete = ref([])
const deleting = ref(false)
const exporting = ref(false)
const showExportError = ref(false)
const exportErrorMessage = ref('')
const showDeleteError = ref(false)
const deleteErrorMessage = ref('')

useDialogFocusRestore(deleteDialog)

// Configuration
const itemsPerPageOptions = [
  { value: 10, title: '10' },
  { value: 25, title: '25' },
  { value: 50, title: '50' },
  { value: 100, title: '100' },
]

const entityTypes = [
  { value: 'person', text: 'Person', icon: 'mdi-account', color: 'indigo' },
  { value: 'company', text: 'Company', icon: 'mdi-office-building', color: 'teal-darken-2' },
  { value: 'domain', text: 'Domain', icon: 'mdi-web', color: 'deep-purple' },
  { value: 'ip_address', text: 'IP Address', icon: 'mdi-ip', color: 'amber-darken-2' },
  { value: 'vehicle', text: 'Vehicle', icon: 'mdi-car', color: 'brown' },
]

const headers = computed(() => [
  { title: 'Type', key: 'entity_type', sortable: true },
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Description', key: 'description', sortable: false },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, align: 'end' },
])

// Watch for filter changes
watch([selectedTypes, search], () => {
  page.value = 1
  selected.value = [] // Clear selection when filters change
  loadItems()
})

// Methods
const loadItems = async () => {
  loading.value = true
  loadErrorMessage.value = ''

  try {
    // For now, use the existing API and implement client-side filtering
    const response = await props.entityService.getCaseEntities(props.caseId)
    let filteredEntities = response || []

    // Apply type filter
    if (selectedTypes.value.length > 0) {
      filteredEntities = filteredEntities.filter((entity) =>
        selectedTypes.value.includes(entity.entity_type),
      )
    }

    // Apply search filter
    if (search.value) {
      const searchTerm = search.value.toLowerCase()
      filteredEntities = filteredEntities.filter((entity) => {
        const name = getEntityName(entity).toLowerCase()
        const description = entity.data.description?.toLowerCase() || ''
        return name.includes(searchTerm) || description.includes(searchTerm)
      })
    }

    // Apply sorting
    if (sortBy.value.length > 0) {
      const sortKey = sortBy.value[0].key
      const sortOrder = sortBy.value[0].order

      filteredEntities.sort((a, b) => {
        let aVal, bVal

        if (sortKey === 'entity_type') {
          aVal = a.entity_type
          bVal = b.entity_type
        } else if (sortKey === 'created_at') {
          aVal = new Date(a.created_at)
          bVal = new Date(b.created_at)
        } else if (sortKey === 'name') {
          aVal = getSortableValue(a)
          bVal = getSortableValue(b)
        } else {
          aVal = getEntityName(a)
          bVal = getEntityName(b)
        }

        if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1
        if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1
        return 0
      })
    } else {
      // Default sort by created_at desc
      filteredEntities.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    }

    // Apply pagination
    totalItems.value = filteredEntities.length
    const startIndex = (page.value - 1) * itemsPerPage.value
    const endIndex = startIndex + itemsPerPage.value
    entities.value = filteredEntities.slice(startIndex, endIndex)
  } catch (error) {
    console.error('Error loading entities:', error)
    entities.value = []
    totalItems.value = 0
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

const getTypeIcon = (type) => {
  return entityTypes.find((t) => t.value === type)?.icon || 'mdi-help'
}

const getTypeLabel = (type) => {
  return entityTypes.find((t) => t.value === type)?.text || type
}

const getTypeColor = (type) => {
  return entityTypes.find((t) => t.value === type)?.color || 'grey'
}

const getSortableValue = (entity) => {
  const name = getEntityName(entity)

  // For IP addresses, convert to a comparable numeric value for proper sorting
  if (entity.entity_type === 'ip_address') {
    const ipParts = name.split('.').map((part) => parseInt(part, 10))
    if (ipParts.length === 4 && ipParts.every((part) => !isNaN(part) && part >= 0 && part <= 255)) {
      // Convert IP to a single number for comparison (IPv4)
      return (ipParts[0] << 24) + (ipParts[1] << 16) + (ipParts[2] << 8) + ipParts[3]
    }
  }

  // For all other entity types, use lowercase string for alphabetical sorting
  return name.toLowerCase()
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

const confirmDelete = (item) => {
  itemsToDelete.value = [item]
  deleteDialog.value = true
}

const confirmBulkDelete = () => {
  itemsToDelete.value = [...selected.value]
  deleteDialog.value = true
}

const cancelDelete = () => {
  deleteDialog.value = false
  itemsToDelete.value = []
}

const performDelete = async () => {
  deleting.value = true
  showDeleteError.value = false

  const targets = [...itemsToDelete.value]
  const results = await Promise.allSettled(
    targets.map((item) => props.entityService.deleteEntity(props.caseId, item.id)),
  )
  const deletedItems = targets.filter((_, index) => results[index].status === 'fulfilled')
  const failedItems = targets.filter((_, index) => results[index].status === 'rejected')

  if (deletedItems.length > 0) {
    emit('deleted', deletedItems)
  }

  selected.value = selected.value.filter((item) => failedItems.some(({ id }) => id === item.id))
  itemsToDelete.value = failedItems
  await loadItems()

  if (failedItems.length > 0) {
    const firstFailure = results.find((result) => result.status === 'rejected')
    console.error('Error deleting entities:', firstFailure.reason)
    deleteErrorMessage.value = `${failedItems.length} ${failedItems.length === 1 ? 'entity' : 'entities'} could not be deleted: ${getErrorMessage(firstFailure.reason, 'deletion service unavailable')}`
    showDeleteError.value = true
  } else {
    deleteDialog.value = false
    selected.value = []
  }

  deleting.value = false
}

const exportEntities = async (format) => {
  if (totalItems.value === 0 || exporting.value) return

  exporting.value = true
  try {
    const download = await props.entityService.exportEntities(props.caseId, {
      format,
      entityTypes: selectedTypes.value,
      search: search.value,
    })
    const date = new Date().toISOString().split('T')[0]
    downloadBlob(download, `case-${props.caseId}-entities-${date}.${format}`)
  } catch (error) {
    console.error('Error exporting entities:', error)
    exportErrorMessage.value = getErrorMessage(error, 'Failed to export entities')
    showExportError.value = true
  } finally {
    exporting.value = false
  }
}

// Expose methods for parent component
defineExpose({
  refresh: loadItems,
})

// Initial load
onMounted(() => {
  loadItems()
})
</script>

<style scoped>
.entity-search {
  min-width: min(100%, 16rem);
  max-width: 18.75rem;
}
</style>
