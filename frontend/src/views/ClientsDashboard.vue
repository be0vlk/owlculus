<template>
  <BaseDashboard title="Clients">
    <v-alert v-if="error" type="error" variant="tonal" class="mb-6" role="alert">
      {{ error }}
    </v-alert>
    <!-- Clients Data Table -->
    <v-card variant="outlined">
      <!-- Header -->
      <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
        <v-icon class="me-3" color="primary" icon="mdi-account-group" size="large" />
        <div class="flex-grow-1">
          <h2 class="text-title-large font-weight-bold">Client Management</h2>
          <div class="text-body-medium text-medium-emphasis">
            Manage client accounts and information
          </div>
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
                aria-label="Refresh client list"
                @click="loadData"
              />
            </template>
          </v-tooltip>
        </div>
      </v-card-title>

      <v-divider />

      <!-- Search Toolbar -->
      <v-card-text class="pa-4">
        <v-row class="mb-0 align-center">
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
                class="operations-search"
                variant="outlined"
              />
            </div>
          </v-col>
        </v-row>
      </v-card-text>

      <v-divider />

      <v-data-table
        :cell-props="{ class: 'operations-cell' }"
        :header-props="{ class: 'operations-column' }"
        :headers="vuetifyHeaders"
        :items="sortedAndFilteredClients"
        :loading="loading"
        class="elevation-0 clients-dashboard-table"
        :hide-no-data="!!error"
        hover
        item-value="id"
        @dblclick:row="handleRowDoubleClick"
      >
        <!-- Created date -->
        <template #[`item.created_at`]="{ item }">
          <span class="text-body-medium">
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
              :aria-label="`Edit ${item.name}`"
              @click="openEditClientModal(item)"
            >
              <v-icon>mdi-pencil</v-icon>
              <v-tooltip activator="parent" location="top"> Edit {{ item.name }} </v-tooltip>
            </v-btn>
            <v-btn
              color="error"
              icon
              size="small"
              variant="outlined"
              @click="handleDelete(item)"
              :aria-label="`Delete ${item.name}`"
            >
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
            <h3 class="text-title-large font-weight-medium mb-2">
              {{ getEmptyStateTitle() }}
            </h3>
            <p class="text-body-medium text-medium-emphasis mb-4">
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
import { useClientsStore } from '../stores/clients'

const { loading, error, searchQuery, clients, loadData, formatDate, sortedAndFilteredClients } =
  useClients()
const clientsStore = useClientsStore()

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
  clientsStore.upsert(newClient)
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
  clientsStore.upsert(updatedClient)
  showNotification(`Client "${updatedClient.name}" updated successfully`, 'success')
}

const handleRowDoubleClick = (event, { item }) => {
  openEditClientModal(item)
}

const handleDelete = async (client) => {
  if (!confirm(`Are you sure you want to delete ${client.name}?`)) return

  try {
    await clientService.deleteClient(client.id)
    clientsStore.remove(client.id)
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
