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
          <v-btn size="small" color="primary" prepend-icon="mdi-plus" @click="openClientModal()">
            Add Client
          </v-btn>
          <v-tooltip location="bottom" text="Refresh client list">
            <template #activator="{ props }">
              <v-btn
                size="small"
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
          <v-col cols="12" md="8" />

          <!-- Search Controls -->
          <v-col cols="12" md="4">
            <div class="d-flex align-center ga-4 justify-end">
              <!-- Search Field -->
              <v-text-field
                v-model="searchQuery"
                clearable
                hide-details
                label="Search clients..."
                prepend-inner-icon="mdi-magnify"
                class="operations-search"
              />
            </div>
          </v-col>
        </v-row>
      </v-card-text>

      <v-divider />

      <v-data-table
        :cell-props="{ class: 'operations-cell' }"
        :header-props="{ class: 'operations-column' }"
        :headers="headers"
        :items="clients"
        :search="searchQuery"
        :sort-by="[{ key: 'name', order: 'asc' }]"
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
              @click="openClientModal(item)"
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
              {{ searchQuery ? 'No clients found' : 'No clients yet' }}
            </h3>
            <p class="text-body-medium text-medium-emphasis mb-4">
              {{
                searchQuery
                  ? "Try adjusting your search terms to find the client you're looking for."
                  : 'Get started by adding your first client to begin managing cases.'
              }}
            </p>
            <v-btn
              v-if="!searchQuery"
              color="primary"
              prepend-icon="mdi-plus"
              @click="openClientModal()"
            >
              Add First Client
            </v-btn>
          </div>
        </template>
      </v-data-table>
    </v-card>
  </BaseDashboard>

  <ClientModal
    :client="selectedClient"
    :is-open="isClientModalOpen"
    @close="isClientModalOpen = false"
    @saved="handleClientSaved"
  />

  <v-snackbar
    v-model="snackbar.show"
    :color="snackbar.color"
    :timeout="snackbar.timeout"
    location="top right"
  >
    {{ snackbar.text }}
    <template #actions>
      <v-btn variant="text" @click="closeNotification"> Close </v-btn>
    </template>
  </v-snackbar>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import BaseDashboard from '../components/BaseDashboard.vue'
import ClientModal from '../components/ClientModal.vue'
import { formatDate } from '../composables/dateUtils'
import { useNotifications } from '../composables/useNotifications'
import { clientService } from '../services/client'
import { useClientsStore } from '../stores/clients'

const clientsStore = useClientsStore()
const { clients } = storeToRefs(clientsStore)
const { snackbar, showNotification, closeNotification } = useNotifications()

const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')

const headers = [
  { title: 'Name', key: 'name' },
  { title: 'Email', key: 'email' },
  { title: 'Phone', key: 'phone' },
  { title: 'Address', key: 'address' },
  { title: 'Created', key: 'created_at' },
  { title: 'Actions', key: 'actions', sortable: false },
]

const loadData = async () => {
  try {
    loading.value = true
    error.value = null
    await clientsStore.refresh()
  } catch (err) {
    error.value = 'Failed to load clients. Please try again later.'
    console.error('Error loading clients:', err)
  } finally {
    loading.value = false
  }
}

const isClientModalOpen = ref(false)
const selectedClient = ref(null)

const openClientModal = (client = null) => {
  selectedClient.value = client
  isClientModalOpen.value = true
}

const handleClientSaved = (client) => {
  clientsStore.upsert(client)
  const action = selectedClient.value ? 'updated' : 'created'
  showNotification(`Client "${client.name}" ${action} successfully`)
}

const handleRowDoubleClick = (event, { item }) => {
  openClientModal(item)
}

const handleDelete = async (client) => {
  if (!confirm(`Are you sure you want to delete ${client.name}?`)) return

  try {
    await clientService.deleteClient(client.id)
    clientsStore.remove(client.id)
    showNotification(`Client "${client.name}" deleted successfully`)
  } catch (error) {
    console.error('Error deleting client:', error)
    showNotification('Failed to delete client. Please try again.', 'error')
  }
}

onMounted(loadData)
</script>
