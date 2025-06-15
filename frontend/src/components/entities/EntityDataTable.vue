<template>
  <div>
    <!-- Quick Filters -->
    <v-row class="mb-4" no-gutters>
      <v-col cols="12">
        <v-chip-group
          v-model="selectedTypes"
          multiple
          filter
          selected-class="text-primary"
        >
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

    <!-- Data Table -->
    <v-data-table-server
      v-model:items-per-page="itemsPerPage"
      v-model:page="page"
      v-model:sort-by="sortBy"
      :headers="headers"
      :items="entities"
      :items-length="totalItems"
      :loading="loading"
      :search="search"
      item-value="id"
      class="elevation-1"
      :items-per-page-options="itemsPerPageOptions"
      :hover="true"
      @update:options="loadItems"
    >
      <!-- Toolbar -->
      <template v-slot:top>
        <v-toolbar flat>
          <v-text-field
            v-model="search"
            prepend-inner-icon="mdi-magnify"
            label="Search entities"
            single-line
            hide-details
            clearable
            density="compact"
            class="mr-4"
            style="max-width: 300px"
          />
          
          <v-spacer />

          <!-- Bulk Actions (disabled for now) -->
          <!--
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
          -->

          <!-- Export Button -->
          <v-btn
            variant="outlined"
            size="small"
            prepend-icon="mdi-download"
            @click="exportEntities"
            class="mr-2"
          >
            Export
          </v-btn>

          <!-- Density Toggle -->
          <v-btn-toggle
            v-model="density"
            density="compact"
            divided
            variant="outlined"
          >
            <v-btn
              icon="mdi-view-list"
              value="compact"
              size="small"
            />
            <v-btn
              icon="mdi-view-stream"
              value="comfortable"
              size="small"
            />
            <v-btn
              icon="mdi-view-module"
              value="default"
              size="small"
            />
          </v-btn-toggle>
        </v-toolbar>
      </template>

      <!-- Type Column -->
      <template v-slot:item.entity_type="{ item }">
        <v-chip
          :color="getTypeColor(item.entity_type)"
          variant="flat"
          size="small"
        >
          <v-icon start size="small">{{ getTypeIcon(item.entity_type) }}</v-icon>
          {{ getTypeLabel(item.entity_type) }}
        </v-chip>
      </template>

      <!-- Name Column -->
      <template v-slot:item.name="{ item }">
        <div class="d-flex align-center">
          <div>
            <div class="font-weight-medium">{{ getEntityName(item) }}</div>
            <div v-if="getEntitySubtitle(item)" class="text-caption text-medium-emphasis">
              {{ getEntitySubtitle(item) }}
            </div>
          </div>
        </div>
      </template>

      <!-- Created Date Column -->
      <template v-slot:item.created_at="{ item }">
        <v-tooltip location="top">
          <template v-slot:activator="{ props }">
            <span v-bind="props">{{ formatDate(item.created_at) }}</span>
          </template>
          {{ formatDateTime(item.created_at) }}
        </v-tooltip>
      </template>

      <!-- Actions Column -->
      <template v-slot:item.actions="{ item }">
        <v-btn
          icon="mdi-eye"
          size="small"
          variant="text"
          @click="$emit('view', item)"
        />
        <v-btn
          icon="mdi-pencil"
          size="small"
          variant="text"
          @click="$emit('edit', item)"
        />
        <v-btn
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
          <v-icon
            size="64"
            color="grey-lighten-1"
            class="mb-4"
          >
            mdi-account-group-outline
          </v-icon>
          <h3 class="text-h6 font-weight-medium mb-2">
            No Entities Found
          </h3>
          <p class="text-body-2 text-medium-emphasis">
            {{ getNoDataMessage() }}
          </p>
          <v-btn
            color="primary"
            prepend-icon="mdi-plus"
            @click="$emit('create')"
            class="mt-4"
          >
            Add First Entity
          </v-btn>
        </v-container>
      </template>

      <!-- Loading -->
      <template v-slot:loading>
        <v-skeleton-loader
          v-for="i in itemsPerPage"
          :key="i"
          type="table-row"
          class="border-b"
        />
      </template>
    </v-data-table-server>

    <!-- Delete Confirmation Dialog -->
    <v-dialog
      v-model="deleteDialog"
      max-width="500"
    >
      <v-card>
        <v-card-title>
          <v-icon start color="error">mdi-alert</v-icon>
          Confirm Delete
        </v-card-title>
        <v-card-text>
          Are you sure you want to delete this entity? 
          This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn
            variant="text"
            @click="deleteDialog = false"
          >
            Cancel
          </v-btn>
          <v-btn
            color="error"
            variant="flat"
            @click="performDelete"
            :loading="deleting"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  caseId: {
    type: Number,
    required: true
  },
  entityService: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['view', 'edit', 'create', 'deleted'])

// Data table state
const entities = ref([])
const loading = ref(false)
const totalItems = ref(0)
const page = ref(1)
const itemsPerPage = ref(25)
const sortBy = ref([])
const search = ref('')
const selected = ref([])
const density = ref('comfortable')

// Filter state
const selectedTypes = ref([])

// Dialog state
const deleteDialog = ref(false)
const itemsToDelete = ref([])
const deleting = ref(false)

// Configuration
const itemsPerPageOptions = [
  { value: 10, title: '10' },
  { value: 25, title: '25' },
  { value: 50, title: '50' },
  { value: 100, title: '100' }
]

const entityTypes = [
  { value: 'person', text: 'Person', icon: 'mdi-account', color: 'blue' },
  { value: 'company', text: 'Company', icon: 'mdi-office-building', color: 'green' },
  { value: 'domain', text: 'Domain', icon: 'mdi-web', color: 'purple' },
  { value: 'ip_address', text: 'IP Address', icon: 'mdi-ip', color: 'orange' }
]

const headers = computed(() => [
  { title: 'Type', key: 'entity_type', sortable: true },
  { title: 'Name', key: 'name', sortable: false },
  { title: 'Description', key: 'description', sortable: false },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, align: 'end' }
])

// Watch for filter changes
watch([selectedTypes, search], () => {
  page.value = 1
  loadItems()
})

// Methods
const loadItems = async (options = {}) => {
  loading.value = true
  
  try {
    // For now, use the existing API and implement client-side filtering
    const response = await props.entityService.getCaseEntities(props.caseId)
    let filteredEntities = response || []

    // Apply type filter
    if (selectedTypes.value.length > 0) {
      filteredEntities = filteredEntities.filter(entity => 
        selectedTypes.value.includes(entity.entity_type)
      )
    }

    // Apply search filter
    if (search.value) {
      const searchTerm = search.value.toLowerCase()
      filteredEntities = filteredEntities.filter(entity => {
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
  } finally {
    loading.value = false
  }
}

const getEntityName = (entity) => {
  switch (entity.entity_type) {
    case 'person':
      const firstName = entity.data.first_name || ''
      const lastName = entity.data.last_name || ''
      return `${firstName} ${lastName}`.trim() || 'Unnamed Person'
    case 'company':
      return entity.data.name || 'Unnamed Company'
    case 'domain':
      return entity.data.domain || 'Unnamed Domain'
    case 'ip_address':
      return entity.data.ip_address || 'Unnamed IP'
    default:
      return 'Unknown Entity'
  }
}

const getEntitySubtitle = (entity) => {
  switch (entity.entity_type) {
    case 'person':
      return entity.data.email
    case 'company':
      return entity.data.website
    case 'domain':
      const subdomainCount = entity.data.subdomains?.length || 0
      return subdomainCount > 0 ? `${subdomainCount} subdomains` : null
    default:
      return null
  }
}

const getTypeIcon = (type) => {
  return entityTypes.find(t => t.value === type)?.icon || 'mdi-help'
}

const getTypeLabel = (type) => {
  return entityTypes.find(t => t.value === type)?.text || type
}

const getTypeColor = (type) => {
  return entityTypes.find(t => t.value === type)?.color || 'grey'
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

const formatDateTime = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  })
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

const performDelete = async () => {
  deleting.value = true
  
  try {
    for (const item of itemsToDelete.value) {
      await props.entityService.deleteEntity(item.id)
    }
    
    emit('deleted', itemsToDelete.value)
    deleteDialog.value = false
    itemsToDelete.value = []
    await loadItems()
  } catch (error) {
    console.error('Error deleting entities:', error)
  } finally {
    deleting.value = false
  }
}

const exportEntities = () => {
  // TODO: Implement CSV export
  console.log('Export entities')
}

// Expose methods for parent component
defineExpose({
  refresh: loadItems
})

// Initial load
onMounted(() => {
  loadItems()
})
</script>

<style scoped>
:deep(.v-data-table-footer) {
  padding: 12px;
}

:deep(.v-data-table) {
  border-radius: 8px;
}
</style>