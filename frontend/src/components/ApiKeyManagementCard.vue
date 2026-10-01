<template>
  <v-card :elevation="0" variant="flat">
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <div class="flex-grow-1">
        <h2 class="text-title-large font-weight-bold">API keys</h2>
        <div class="text-body-medium text-medium-emphasis">
          Manage API keys for external services and plugins
        </div>
      </div>
      <v-btn
        size="small"
        color="primary"
        prepend-icon="mdi-plus"
        @click="openDialog()"
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
      <v-alert v-else-if="error" :text="error" class="ma-4" type="error" variant="tonal" />

      <!-- Empty state -->
      <div v-else-if="!apiKeys.length" class="pa-8 text-center">
        <v-icon icon="mdi-key-off" size="64" color="grey-darken-1" class="mb-4" />
        <div class="text-title-large text-medium-emphasis mb-2">No API Keys Configured</div>
        <div class="text-body-medium text-medium-emphasis mb-4">
          Add API keys to enable external service integrations and plugins
        </div>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="openDialog()">
          Add Your First API Key
        </v-btn>
      </div>

      <!-- API Keys Table -->
      <v-table v-else class="admin-dashboard-table">
        <thead>
          <tr>
            <th class="operations-column">Provider</th>
            <th class="operations-column">Name</th>
            <th class="operations-column">API Key</th>
            <th class="operations-column">Created</th>
            <th class="operations-column">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="apiKey in apiKeys" :key="apiKey.provider">
            <td class="operations-cell">
              <div class="d-flex align-center">
                <v-icon
                  :color="apiKey.is_configured ? 'success' : 'grey'"
                  :icon="findProvider(apiKey.provider)?.icon || 'mdi-key'"
                  class="me-3"
                />
                <span class="font-weight-medium">{{ providerName(apiKey.provider) }}</span>
              </div>
            </td>
            <td class="operations-cell">
              <span class="font-weight-medium">{{ apiKey.name }}</span>
            </td>
            <td class="operations-cell">
              <v-chip
                size="small"
                variant="tonal"
                :color="apiKey.is_configured ? 'success' : 'grey'"
                class="font-mono"
              >
                ••••••••••••
              </v-chip>
            </td>
            <td class="operations-cell">
              <span v-if="apiKey.created_at" class="text-body-medium">
                {{ formatDateOnly(apiKey.created_at) }}
              </span>
              <span v-else class="text-body-small text-medium-emphasis">Unknown</span>
            </td>
            <td class="operations-cell">
              <div class="d-flex align-center" style="gap: 8px">
                <v-btn
                  size="small"
                  variant="outlined"
                  icon
                  @click="openDialog(apiKey)"
                  :disabled="saving || deleting"
                  :aria-label="`Edit ${providerName(apiKey.provider)} API Key`"
                >
                  <v-icon>mdi-pencil</v-icon>
                  <v-tooltip activator="parent" location="top">
                    Edit {{ providerName(apiKey.provider) }} API Key
                  </v-tooltip>
                </v-btn>
                <v-btn
                  color="error"
                  size="small"
                  variant="outlined"
                  icon
                  @click="handleDeleteApiKey(apiKey)"
                  :disabled="saving || deleting"
                  :aria-label="`Delete ${providerName(apiKey.provider)} API Key`"
                >
                  <v-icon>mdi-delete</v-icon>
                  <v-tooltip activator="parent" location="top">
                    Delete {{ providerName(apiKey.provider) }} API Key
                  </v-tooltip>
                </v-btn>
              </div>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card-text>

    <v-dialog :aria-label="dialogTitle" v-model="showDialog" max-width="600">
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon :icon="editing ? 'mdi-pencil' : 'mdi-plus'" class="me-3" />
          {{ editing ? `${dialogTitle} - ${providerName(form.provider)}` : dialogTitle }}
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <v-form
            :id="formId"
            ref="formRef"
            v-model="valid"
            :disabled="saving"
            @submit.prevent="save"
          >
            <v-row>
              <template v-if="!editing">
                <v-col cols="12">
                  <v-select
                    v-model="form.provider"
                    :items="PROVIDERS"
                    item-title="text"
                    item-value="value"
                    label="Provider"
                    prepend-inner-icon="mdi-web"
                    :rules="[validateProvider]"
                    @update:model-value="suggestName"
                    required
                  >
                    <template #item="{ props, item }">
                      <v-list-item v-bind="props">
                        <template #prepend>
                          <v-icon :icon="item.icon" />
                        </template>
                      </v-list-item>
                    </template>
                  </v-select>
                </v-col>

                <v-col cols="12" v-if="form.provider === 'custom'">
                  <v-text-field
                    v-model="form.provider"
                    label="Custom Provider Name"
                    prepend-inner-icon="mdi-identifier"
                    :rules="[validateProvider]"
                    hint="Use lowercase letters, numbers, underscores, and hyphens only"
                    persistent-hint
                    required
                  />
                </v-col>
              </template>

              <v-col cols="12">
                <v-text-field
                  v-model="form.name"
                  label="Display Name"
                  prepend-inner-icon="mdi-tag"
                  :rules="[(v) => !!v || 'Name is required']"
                  :hint="editing ? undefined : 'Friendly name for this API key'"
                  :persistent-hint="!editing"
                  required
                />
              </v-col>

              <v-col cols="12">
                <v-text-field
                  v-model="form.api_key"
                  label="API Key"
                  prepend-inner-icon="mdi-key"
                  :type="showKey ? 'text' : 'password'"
                  :append-inner-icon="showKey ? 'mdi-eye' : 'mdi-eye-off'"
                  @click:append-inner="showKey = !showKey"
                  :rules="editing ? [] : [validateApiKey]"
                  :hint="
                    editing
                      ? 'Enter the new API key (leave empty to keep current key)'
                      : 'Enter the API key provided by the service'
                  "
                  persistent-hint
                  :placeholder="editing ? 'Enter new API key to update' : undefined"
                  :required="!editing"
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>

        <v-divider />

        <v-card-actions class="pa-4 flex-wrap">
          <v-spacer />
          <v-btn :disabled="saving" variant="text" @click="showDialog = false"> Cancel </v-btn>
          <v-btn color="primary" :loading="saving" :disabled="!valid" type="submit" :form="formId">
            {{ editing ? 'Update API Key' : 'Add API Key' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { computed, onMounted, ref, useId } from 'vue'
import api from '@/services/api'
import { formatDateOnly } from '@/composables/dateUtils'

const emit = defineEmits(['notification', 'confirmDelete'])

const PROVIDERS = [
  { text: 'OpenAI', value: 'openai', icon: 'mdi-robot' },
  { text: 'Security Trails', value: 'securitytrails', icon: 'mdi-magnify-scan' },
  { text: 'People Data Labs', value: 'people_data_labs', icon: 'mdi-account-group' },
  { text: 'Shodan', value: 'shodan', icon: 'mdi-radar' },
  { text: 'VirusTotal', value: 'virustotal', icon: 'mdi-shield-bug' },
  { text: 'Custom', value: 'custom', icon: 'mdi-plus' },
]
const findProvider = (value) => PROVIDERS.find((p) => p.value === value)
const capitalize = (value) => value.charAt(0).toUpperCase() + value.slice(1)
const providerName = (value) => findProvider(value)?.text || capitalize(value)

const apiKeys = ref([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const error = ref(null)

const formId = useId()
const formRef = ref(null)
const valid = ref(false)
const showDialog = ref(false)
const showKey = ref(false)
const editing = ref(false)
const form = ref({ provider: '', name: '', api_key: '' })
const dialogTitle = computed(() => (editing.value ? 'Edit API Key' : 'Add API Key'))

const validateProvider = (value) => {
  if (!value) return 'Provider is required'
  if (!/^[a-z0-9_-]+$/i.test(value)) {
    return 'Provider must contain only letters, numbers, underscores, and hyphens'
  }
  return true
}

const validateApiKey = (value) => {
  if (!value) return 'API key is required'
  if (value.length < 8) return 'API key must be at least 8 characters'
  return true
}

const suggestName = (value) => {
  if (value !== 'custom' && findProvider(value) && !form.value.name) {
    form.value.name = `${findProvider(value).text} API`
  }
}

const loadApiKeys = async () => {
  loading.value = true
  error.value = null
  try {
    const { data } = await api.get('/api/admin/configuration/api-keys')
    apiKeys.value = Object.entries(data)
      .map(([provider, key]) => ({
        provider,
        name: key.name || `${capitalize(provider)} API`,
        is_configured: key.is_configured !== false,
        created_at: key.created_at,
      }))
      .sort((a, b) => a.provider.localeCompare(b.provider))
  } catch (err) {
    console.error('Error loading API keys:', err)
    error.value = 'Failed to load API keys'
    apiKeys.value = []
  } finally {
    loading.value = false
  }
}

const openDialog = (apiKey) => {
  editing.value = !!apiKey
  // Never pre-fill the stored key.
  form.value = { provider: apiKey?.provider ?? '', name: apiKey?.name ?? '', api_key: '' }
  showDialog.value = true
}

// Adding and editing send the same PUT; an empty key keeps the stored one.
const save = async () => {
  if (saving.value) return
  const { valid } = await formRef.value.validate()
  if (!valid || saving.value) return
  const action = editing.value ? 'update' : 'add'
  const { provider, name, api_key } = form.value
  saving.value = true
  try {
    await api.put(
      `/api/admin/configuration/api-keys/${provider}`,
      api_key ? { name, api_key } : { name },
    )
    await loadApiKeys()
    showDialog.value = false
    emit('notification', {
      text: `API key ${editing.value ? 'updated' : 'added'} successfully!`,
      color: 'success',
    })
  } catch (err) {
    emit('notification', {
      text: err.response?.data?.detail || `Failed to ${action} API key`,
      color: 'error',
    })
  } finally {
    saving.value = false
  }
}

const handleDeleteApiKey = (apiKey) => {
  emit('confirmDelete', {
    title: 'Delete API Key',
    message: `Are you sure you want to delete the API key for "${providerName(apiKey.provider)}"?`,
    warning:
      'This action cannot be undone. Any plugins or services using this API key will stop working.',
    onConfirm: async () => {
      deleting.value = true
      try {
        await api.delete(`/api/admin/configuration/api-keys/${apiKey.provider}`)
        await loadApiKeys()
        emit('notification', { text: 'API key deleted successfully!', color: 'success' })
      } catch (err) {
        emit('notification', {
          text: err.response?.data?.detail || 'Failed to delete API key',
          color: 'error',
        })
      } finally {
        deleting.value = false
      }
    },
  })
}

onMounted(loadApiKeys)
</script>

<style scoped>
.font-mono {
  font-family: 'Roboto Mono', monospace;
}
</style>
