<template>
  <BaseDashboard :error="error" :loading="loading" title="Clients">
    <!-- Clients Data Table -->
    <v-card variant="outlined">
      <!-- Header -->
      <v-card-title class="d-flex align-center pa-4 bg-surface">
        <v-icon class="me-3" color="primary" icon="mdi-account-group" size="large" />
        <div class="flex-grow-1">
          <div class="text-h6 font-weight-bold">Client Management</div>
          <div class="text-body-2 text-medium-emphasis">Manage client accounts and information</div>
        </div>
        <div class="d-flex align-center ga-2">
          <v-btn color="primary" prepend-icon="mdi-plus" variant="flat" @click="openNewClientModal">
            Add Client
          </v-btn>
          <v-tooltip location="bottom" text="Refresh client list">
            <template #activator="{ props }">
              <v-btn
                :loading="loading"
                icon="mdi-refresh"
                v-bind="props"
                variant="outlined"
                @click="loadData"
              />
            </template>
          </v-tooltip>
        </div>
      </v-card-title>

      <v-divider />

      <!-- Search Toolbar -->
      <v-card-text class="pa-4">
        <v-row align="center" class="mb-0">
          <v-col cols="12" md="8">
            <!-- Could add filters here in the future -->
          </v-col>

          <!-- Search Controls -->
          <v-col cols="12" md="4">
            <div class="d-flex align-center ga-4 justify-end">
              <!-- Search Field -->
              <v-text-field
                v-model="searchQuery"
                clearable
                density="comfortable"
                hide-details
                label="Search clients..."
                prepend-inner-icon="mdi-magnify"
                style="min-width: 280px"
                variant="outlined"
              />
            </div>
          </v-col>
        </v-row>
      </v-card-text>

      <v-divider />

      <v-data-table
        :headers="vuetifyHeaders"
        :items="sortedAndFilteredClients"
        :loading="loading"
        class="elevation-0 clients-dashboard-table"
        hover
        item-key="id"
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
          <div class="d-flex ga-2">
            <v-btn
              color="info"
              icon
              size="small"
              variant="outlined"
              @click="openEditClientModal(item)"
            >
              <v-icon>mdi-pencil</v-icon>
              <v-tooltip activator="parent" location="top"> Edit {{ item.name }} </v-tooltip>
            </v-btn>
            <v-btn color="error" icon size="small" variant="outlined" @click="handleDelete(item)">
              <v-icon>mdi-delete</v-icon>
              <v-tooltip activator="parent" location="top"> Delete {{ item.name }} </v-tooltip>
            </v-btn>
          </div>
        </template>

        <!-- Empty state -->
        <template #no-data>
          <div class="text-center pa-12">
            <v-icon
              class="mb-4"
              color="grey-lighten-1"
              icon="mdi-account-group-outline"
              size="64"
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
  </BaseDashboard>

  <!-- New Client Modal -->
  <NewClientModal
    :is-open="isNewClientModalOpen"
    @close="closeNewClientModal"
    @created="handleClientCreated"
  />

  <!-- Edit Client Modal -->
  <EditClientModal
    :client="selectedClient"
    :is-open="isEditClientModalOpen"
    @close="closeEditClientModal"
    @updated="handleClientUpdated"
  />

  <!-- Snackbar for notifications -->
  <v-snackbar
    v-model="snackbar.show"
    :color="snackbar.color"
    :timeout="snackbar.timeout"
    location="top right"
  >
    {{ snackbar.text }}
    <template #actions>
      <v-btn variant="text" @click="snackbar.show = false"> Close </v-btn>
    </template>
  </v-snackbar>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import BaseDashboard from '../components/BaseDashboard.vue'
import NewClientModal from '../components/NewClientModal.vue'
import EditClientModal from '../components/EditClientModal.vue'
import { useClients } from '../composables/useClients'
import { clientService } from '../services/client'

const { loading, error, searchQuery, clients, loadData, formatDate, sortedAndFilteredClients } =
  useClients()

// Vuetify table headers
const vuetifyHeaders = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Email', key: 'email', sortable: true },
  { title: 'Phone', key: 'phone', sortable: true },
  { title: 'Address', key: 'address', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false },
]

const isNewClientModalOpen = ref(false)
const isEditClientModalOpen = ref(false)
const selectedClient = ref(null)

// Snackbar state
const snackbar = ref({
  show: false,
  text: '',
  color: 'success',
  timeout: 4000,
})

const openNewClientModal = () => {
  isNewClientModalOpen.value = true
}

const closeNewClientModal = () => {
  isNewClientModalOpen.value = false
}

const handleClientCreated = (newClient) => {
  clients.value.push(newClient)
  showNotification(`Client "${newClient.name}" created successfully`, 'success')
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
  const index = clients.value.findIndex((c) => c.id === updatedClient.id)
  if (index !== -1) {
    clients.value[index] = updatedClient
    showNotification(`Client "${updatedClient.name}" updated successfully`, 'success')
  }
}

const handleRowDoubleClick = (event, { item }) => {
  openEditClientModal(item)
}

const handleDelete = async (client) => {
  if (!confirm(`Are you sure you want to delete ${client.name}?`)) return

  try {
    await clientService.deleteClient(client.id)
    clients.value = clients.value.filter((c) => c.id !== client.id)
    showNotification(`Client "${client.name}" deleted successfully`, 'success')
  } catch (error) {
    console.error('Error deleting client:', error)
    showNotification('Failed to delete client. Please try again.', 'error')
  }
}

// Snackbar helper function
const showNotification = (text, color = 'success') => {
  snackbar.value.text = text
  snackbar.value.color = color
  snackbar.value.show = true
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
    return "Try adjusting your search terms to find the client you're looking for."
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
  background-color: rgb(var(--v-theme-primary), 0.04) !important;
  cursor: pointer;
}

.clients-dashboard-table :deep(.v-data-table__td) {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.08) !important;
}

.clients-dashboard-table :deep(.v-data-table__th) {
  padding: 16px !important;
  font-weight: 600 !important;
  color: rgb(var(--v-theme-on-surface), 0.87) !important;
  border-bottom: 2px solid rgb(var(--v-theme-on-surface), 0.12) !important;
}

.clients-dashboard-table :deep(.v-data-table-rows-no-data) {
  padding: 48px 16px !important;
}
</style>
