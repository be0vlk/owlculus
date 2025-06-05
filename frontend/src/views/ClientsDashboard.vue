<template>
  <v-app>
    <Sidebar />
    
    <v-main>
      <v-container class="pa-6">
        <!-- Page Header -->
        <div class="mb-6">
          <v-row align="center" justify="space-between">
            <v-col>
              <h1 class="text-h4 font-weight-bold">
                Clients Dashboard
              </h1>
            </v-col>
            <v-col cols="auto">
              <v-btn
                color="primary"
                prepend-icon="mdi-plus"
                @click="openNewClientModal"
              >
                Add Client
              </v-btn>
            </v-col>
          </v-row>
        </div>

        <!-- Loading state -->
        <v-card v-if="loading">
          <v-card-title class="d-flex align-center justify-end pa-6">
            <v-skeleton-loader type="text" width="300" />
          </v-card-title>
          <v-skeleton-loader 
            type="table" 
            class="ma-4"
          />
        </v-card>

        <!-- Error state -->
        <v-alert
          v-else-if="error"
          type="error"
          class="ma-4"
          :text="error"
          prominent
          border="start"
        />

        <!-- Clients Data Table -->
        <v-card v-else>
          <v-card-title class="d-flex align-center justify-end">
            <!-- Search Field -->
            <v-text-field
              v-model="searchQuery"
              prepend-inner-icon="mdi-magnify"
              label="Search clients..."
              variant="outlined"
              density="compact"
              hide-details
              style="min-width: 300px;"
            />
          </v-card-title>

          <v-data-table
            :headers="vuetifyHeaders"
            :items="sortedAndFilteredClients"
            :loading="loading"
            item-key="id"
            class="elevation-0 clients-dashboard-table"
            hover
            @dblclick:row="handleRowDoubleClick"
          >
            <!-- Created date -->
            <template #[`item.created_at`]="{ item }">
              <span class="text-body-2">
                {{ formatDate(item.created_at) }}
              </span>
            </template>

            <!-- Actions column -->
            <template #[`item.actions`]="{ item }">
              <v-btn
                color="error"
                size="small"
                variant="outlined"
                icon
                @click="handleDelete(item)"
              >
                <v-icon>mdi-delete</v-icon>
                <v-tooltip activator="parent" location="top">
                  Delete {{ item.name }}
                </v-tooltip>
              </v-btn>
            </template>

            <!-- Empty state -->
            <template #no-data>
              <div class="text-center pa-12">
                <v-icon
                  icon="mdi-account-group-outline"
                  size="64"
                  color="grey-lighten-1"
                  class="mb-4"
                />
                <h3 class="text-h6 font-weight-medium mb-2">
                  {{ getEmptyStateTitle() }}
                </h3>
                <p class="text-body-2 text-medium-emphasis mb-4">
                  {{ getEmptyStateMessage() }}
                </p>
                <v-btn
                  v-if="shouldShowCreateButton()"
                  color="primary"
                  prepend-icon="mdi-plus"
                  @click="openNewClientModal"
                >
                  Add First Client
                </v-btn>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-container>
    </v-main>

    <!-- New Client Modal -->
    <NewClientModal
      :is-open="isNewClientModalOpen"
      @close="closeNewClientModal"
      @created="handleClientCreated"
    />

    <!-- Edit Client Modal -->
    <EditClientModal
      :is-open="isEditClientModalOpen"
      :client="selectedClient"
      @close="closeEditClientModal"
      @updated="handleClientUpdated"
    />
  </v-app>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Sidebar from '../components/Sidebar.vue'
import NewClientModal from '../components/NewClientModal.vue'
import EditClientModal from '../components/EditClientModal.vue'
import { useClients } from '../composables/useClients'
import { clientService } from '../services/client'

const {
  loading,
  error,
  searchQuery,
  clients,
  loadData,
  formatDate,
  sortedAndFilteredClients
} = useClients()

// Vuetify table headers
const vuetifyHeaders = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Email', key: 'email', sortable: true },
  { title: 'Phone', key: 'phone', sortable: true },
  { title: 'Address', key: 'address', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]

const isNewClientModalOpen = ref(false)
const isEditClientModalOpen = ref(false)
const selectedClient = ref(null)

const openNewClientModal = () => {
  isNewClientModalOpen.value = true
}

const closeNewClientModal = () => {
  isNewClientModalOpen.value = false
}

const handleClientCreated = (newClient) => {
  clients.value.push(newClient)
}

const openEditClientModal = (client) => {
  selectedClient.value = client
  isEditClientModalOpen.value = true
}

const closeEditClientModal = () => {
  isEditClientModalOpen.value = false
  selectedClient.value = null
}

const handleClientUpdated = (updatedClient) => {
  const index = clients.value.findIndex(c => c.id === updatedClient.id)
  if (index !== -1) {
    clients.value[index] = updatedClient
  }
}

const handleRowDoubleClick = (event, { item }) => {
  openEditClientModal(item)
}

const handleDelete = async (client) => {
  if (!confirm(`Are you sure you want to delete ${client.name}?`)) return

  try {
    await clientService.deleteClient(client.id)
    clients.value = clients.value.filter(c => c.id !== client.id)
  } catch (error) {
    console.error('Error deleting client:', error)
  }
}


// Empty state functions
const getEmptyStateTitle = () => {
  if (searchQuery.value) {
    return 'No clients found'
  } else if ((clients.value || []).length === 0) {
    return 'No clients yet'
  } else {
    return 'No clients match your search'
  }
}

const getEmptyStateMessage = () => {
  if (searchQuery.value) {
    return 'Try adjusting your search terms to find the client you\'re looking for.'
  } else if ((clients.value || []).length === 0) {
    return 'Get started by adding your first client to begin managing cases.'
  } else {
    return 'Try adjusting your search to see more clients.'
  }
}

const shouldShowCreateButton = () => {
  return (clients.value || []).length === 0 && !searchQuery.value
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.clients-dashboard-table :deep(.v-data-table__tr:hover) {
  background-color: rgba(var(--v-theme-primary), 0.04) !important;
  cursor: pointer;
}

.clients-dashboard-table :deep(.v-data-table__td) {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08) !important;
}

.clients-dashboard-table :deep(.v-data-table__th) {
  padding: 16px !important;
  font-weight: 600 !important;
  color: rgba(var(--v-theme-on-surface), 0.87) !important;
  border-bottom: 2px solid rgba(var(--v-theme-on-surface), 0.12) !important;
}

.clients-dashboard-table :deep(.v-data-table-rows-no-data) {
  padding: 48px 16px !important;
}
</style>