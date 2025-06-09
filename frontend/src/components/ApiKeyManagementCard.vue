<template>
  <v-card class="mb-6" variant="outlined">
    <v-card-title class="d-flex align-center pa-4 bg-surface">
      <v-icon icon="mdi-key" color="primary" size="large" class="me-3" />
      <div class="flex-grow-1">
        <div class="text-h6 font-weight-bold">API Key Management</div>
        <div class="text-body-2 text-medium-emphasis">Manage API keys for external services and plugins</div>
      </div>
      <v-btn
        color="primary"
        variant="flat"
        prepend-icon="mdi-plus"
        @click="openAddDialog"
        :disabled="loading"
      >
        Add API Key
      </v-btn>
    </v-card-title>

    <v-divider />

    <v-card-text class="pa-0">
      <!-- Loading state -->
      <div v-if="loading" class="pa-6">
        <v-skeleton-loader type="table-row@3" />
      </div>

      <!-- Error state -->
      <v-alert
        v-else-if="error"
        type="error"
        variant="tonal"
        class="ma-4"
        :text="error"
      />

      <!-- Empty state -->
      <div v-else-if="!sortedApiKeys.length" class="pa-8 text-center">
        <v-icon icon="mdi-key-off" size="64" color="grey-darken-1" class="mb-4" />
        <div class="text-h6 text-medium-emphasis mb-2">No API Keys Configured</div>
        <div class="text-body-2 text-medium-emphasis mb-4">
          Add API keys to enable external service integrations and plugins
        </div>
        <v-btn
          color="primary"
          variant="flat"
          prepend-icon="mdi-plus"
          @click="openAddDialog"
        >
          Add Your First API Key
        </v-btn>
      </div>

      <!-- API Keys Table -->
      <v-table v-else class="admin-dashboard-table">
        <thead>
          <tr>
            <th>Provider</th>
            <th>Name</th>
            <th>API Key</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="apiKey in sortedApiKeys" :key="apiKey.provider">
            <td>
              <div class="d-flex align-center">
                <v-icon 
                  :icon="getProviderIcon(apiKey.provider)" 
                  class="me-3" 
                  :color="apiKey.is_configured ? 'success' : 'grey'" 
                />
                <span class="font-weight-medium">{{ getProviderDisplayName(apiKey.provider) }}</span>
              </div>
            </td>
            <td>
              <span class="font-weight-medium">{{ apiKey.name }}</span>
            </td>
            <td>
              <v-chip
                size="small"
                variant="tonal"
                :color="apiKey.is_configured ? 'success' : 'grey'"
                class="font-mono"
              >
                {{ apiKey.masked_key }}
              </v-chip>
            </td>
            <td>
              <span v-if="apiKey.created_at" class="text-body-2">
                {{ formatDate(apiKey.created_at) }}
              </span>
              <span v-else class="text-caption text-medium-emphasis">Unknown</span>
            </td>
            <td>
              <div class="d-flex align-center" style="gap: 8px;">
                <v-btn
                  color="primary"
                  size="small"
                  variant="outlined"
                  icon
                  @click="openEditDialog(apiKey)"
                  :disabled="saving || deleting"
                >
                  <v-icon>mdi-pencil</v-icon>
                  <v-tooltip activator="parent" location="top">
                    Edit {{ getProviderDisplayName(apiKey.provider) }} API Key
                  </v-tooltip>
                </v-btn>
                <v-btn
                  color="error"
                  size="small"
                  variant="outlined"
                  icon
                  @click="handleDeleteApiKey(apiKey)"
                  :disabled="saving || deleting"
                >
                  <v-icon>mdi-delete</v-icon>
                  <v-tooltip activator="parent" location="top">
                    Delete {{ getProviderDisplayName(apiKey.provider) }} API Key
                  </v-tooltip>
                </v-btn>
              </div>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card-text>

    <!-- Add API Key Dialog -->
    <v-dialog v-model="showAddDialog" max-width="600">
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon icon="mdi-plus" class="me-3" />
          Add API Key
        </v-card-title>
        
        <v-divider />
        
        <v-card-text class="pa-4">
          <v-form @submit.prevent="handleAddApiKey">
            <v-row>
              <v-col cols="12">
                <v-select
                  v-model="newKeyForm.provider"
                  :items="commonProviders"
                  item-title="text"
                  item-value="value"
                  label="Provider"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-web"
                  :rules="[validateProvider]"
                  @update:model-value="handleProviderChange(newKeyForm.provider, newKeyForm)"
                  required
                >
                  <template #item="{ props, item }">
                    <v-list-item v-bind="props">
                      <template #prepend>
                        <v-icon :icon="item.raw.icon" />
                      </template>
                    </v-list-item>
                  </template>
                </v-select>
              </v-col>
              
              <v-col cols="12" v-if="newKeyForm.provider === 'custom'">
                <v-text-field
                  v-model="newKeyForm.provider"
                  label="Custom Provider Name"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-identifier"
                  :rules="[validateProvider]"
                  hint="Use lowercase letters, numbers, underscores, and hyphens only"
                  persistent-hint
                  required
                />
              </v-col>
              
              <v-col cols="12">
                <v-text-field
                  v-model="newKeyForm.name"
                  label="Display Name"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-tag"
                  :rules="[validateName]"
                  hint="Friendly name for this API key"
                  persistent-hint
                  required
                />
              </v-col>
              
              <v-col cols="12">
                <v-text-field
                  v-model="newKeyForm.api_key"
                  label="API Key"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-key"
                  :type="showNewKeyPassword ? 'text' : 'password'"
                  :append-inner-icon="showNewKeyPassword ? 'mdi-eye' : 'mdi-eye-off'"
                  @click:append-inner="showNewKeyPassword = !showNewKeyPassword"
                  :rules="[validateApiKey]"
                  hint="Enter the API key provided by the service"
                  persistent-hint
                  required
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        
        <v-divider />
        
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn
            variant="text"
            @click="closeAddDialog"
            :disabled="saving"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="saving"
            :disabled="!isFormValid"
            @click="handleAddApiKey"
          >
            Add API Key
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Edit API Key Dialog -->
    <v-dialog v-model="showEditDialog" max-width="600">
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon icon="mdi-pencil" class="me-3" />
          Edit API Key - {{ getProviderDisplayName(editingProvider) }}
        </v-card-title>
        
        <v-divider />
        
        <v-card-text class="pa-4">
          <v-form @submit.prevent="handleUpdateApiKey">
            <v-row>
              <v-col cols="12">
                <v-text-field
                  v-model="editKeyForm.name"
                  label="Display Name"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-tag"
                  :rules="[validateName]"
                  required
                />
              </v-col>
              
              <v-col cols="12">
                <v-text-field
                  v-model="editKeyForm.api_key"
                  label="API Key"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-key"
                  :type="showEditKeyPassword ? 'text' : 'password'"
                  :append-inner-icon="showEditKeyPassword ? 'mdi-eye' : 'mdi-eye-off'"
                  @click:append-inner="showEditKeyPassword = !showEditKeyPassword"
                  hint="Enter the new API key (leave empty to keep current key)"
                  persistent-hint
                  placeholder="Enter new API key to update"
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        
        <v-divider />
        
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn
            variant="text"
            @click="closeEditDialog"
            :disabled="saving"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="saving"
            :disabled="!editKeyForm.name"
            @click="handleUpdateApiKey"
          >
            Update API Key
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useApiKeys } from '@/composables/useApiKeys'

const emit = defineEmits(['notification', 'confirmDelete'])

// Password visibility toggles
const showNewKeyPassword = ref(false)
const showEditKeyPassword = ref(false)

// Use the API keys composable
const {
  // State
  loading,
  saving,
  deleting,
  error,
  showAddDialog,
  showEditDialog,
  editingProvider,
  newKeyForm,
  editKeyForm,
  
  // Constants
  commonProviders,
  
  // Computed
  sortedApiKeys,
  isFormValid,
  
  // Validation
  validateProvider,
  validateApiKey,
  validateName,
  
  // Methods
  loadApiKeys,
  addApiKey,
  updateApiKey,
  deleteApiKey,
  openAddDialog,
  openEditDialog,
  closeAddDialog,
  closeEditDialog,
  handleProviderChange,
  getProviderIcon,
  getProviderDisplayName
} = useApiKeys()

// Event handlers
const handleAddApiKey = async () => {
  try {
    await addApiKey()
    emit('notification', { text: 'API key added successfully!', color: 'success' })
  } catch (error) {
    console.error('Error adding API key:', error)
    emit('notification', { text: error.message || 'Failed to add API key', color: 'error' })
  }
}

const handleUpdateApiKey = async () => {
  try {
    await updateApiKey()
    emit('notification', { text: 'API key updated successfully!', color: 'success' })
  } catch (error) {
    console.error('Error updating API key:', error)
    emit('notification', { text: error.message || 'Failed to update API key', color: 'error' })
  }
}

const handleDeleteApiKey = async (apiKey) => {
  try {
    await emit('confirmDelete', {
      title: 'Delete API Key',
      message: `Are you sure you want to delete the API key for "${getProviderDisplayName(apiKey.provider)}"?`,
      warning: 'This action cannot be undone. Any plugins or services using this API key will stop working.',
      onConfirm: async () => {
        await deleteApiKey(apiKey.provider)
        emit('notification', { text: 'API key deleted successfully!', color: 'success' })
      }
    })
  } catch (error) {
    if (error.message && !error.message.includes('cancelled')) {
      console.error('Error deleting API key:', error)
      emit('notification', { text: error.message || 'Failed to delete API key', color: 'error' })
    }
  }
}

// Utility functions
const formatDate = (dateString) => {
  if (!dateString) return 'Unknown'
  try {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  } catch {
    return 'Invalid date'
  }
}

// Load API keys on mount
onMounted(async () => {
  try {
    await loadApiKeys()
  } catch (error) {
    console.error('Error loading API keys:', error)
  }
})
</script>

<style scoped>
.font-mono {
  font-family: 'Roboto Mono', monospace;
}

.admin-dashboard-table :deep(.v-data-table__tr:hover) {
  background-color: rgb(var(--v-theme-primary), 0.04) !important;
}

.admin-dashboard-table :deep(.v-data-table__td) {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.08) !important;
}

.admin-dashboard-table :deep(.v-data-table__th) {
  padding: 16px !important;
  font-weight: 600 !important;
  color: rgb(var(--v-theme-on-surface), 0.87) !important;
  border-bottom: 2px solid rgb(var(--v-theme-on-surface), 0.12) !important;
}
</style>