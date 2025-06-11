<template>
  <BaseDashboard 
    title="Plugins" 
    :loading="loading" 
    :error="error"
  >
    <template #loading>
      <v-card variant="outlined">
        <v-card-title class="d-flex align-center pa-4 bg-surface">
          <v-skeleton-loader type="text" width="200" />
          <v-spacer />
          <v-skeleton-loader type="button" width="120" />
        </v-card-title>
        <v-divider />
        <v-card-text class="text-center pa-16">
          <v-progress-circular
            size="64"
            width="4"
            color="primary"
            indeterminate
          />
          <div class="text-h6 mt-4">Loading plugins...</div>
        </v-card-text>
      </v-card>
    </template>

    <!-- Main Content -->
          <!-- Plugin Management Card -->
          <v-card variant="outlined">
            <!-- Header -->
            <v-card-title class="d-flex align-center pa-4 bg-surface">
              <v-icon icon="mdi-puzzle" color="primary" size="large" class="me-3" />
              <div class="flex-grow-1">
                <div class="text-h6 font-weight-bold">Plugin Management</div>
                <div class="text-body-2 text-medium-emphasis">Execute OSINT plugins and analyze results</div>
              </div>
              <div class="d-flex align-center ga-2">
                <v-tooltip text="Refresh plugins list" location="bottom">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      icon="mdi-refresh"
                      variant="outlined"
                      @click="loadPlugins"
                      :loading="loading"
                    />
                  </template>
                </v-tooltip>
              </div>
            </v-card-title>

            <v-divider />

            <!-- Category Tabs Toolbar -->
            <v-card-text class="pa-4">
              <v-row align="center" class="mb-0">
                <v-col cols="12">
                  <div class="d-flex align-center ga-2">
                    <span class="text-body-2 font-weight-medium me-2">Categories:</span>
                    <v-chip-group
                      v-model="selectedCategories"
                      selected-class="text-primary"
                      color="primary"
                      variant="outlined"
                      multiple
                    >
                      <v-chip
                        value="All"
                        filter
                        size="small"
                      >
                        All
                      </v-chip>
                      <v-chip
                        v-for="category in categories"
                        :key="category"
                        :value="category"
                        filter
                        size="small"
                      >
                        {{ category }}
                      </v-chip>
                    </v-chip-group>
                  </div>
                </v-col>
              </v-row>
            </v-card-text>

            <v-divider />

            <!-- Plugin Grid -->
            <v-card-text class="pa-4">
              <v-row v-if="Object.keys(filteredPlugins).length">
                <v-col
                  v-for="(plugin, name) in filteredPlugins"
                  :key="name"
                  cols="12"
                  md="6"
                  lg="4"
                >
                  <v-card
                    :class="{ 'h-100': expandedCards[name] }"
                    variant="outlined"
                    :ripple="false"
                    @click="toggleCard(name)"
                    style="cursor: pointer;"
                    hover
                  >
                    <v-card-text class="pa-4">
                      <div class="d-flex justify-space-between align-start mb-3">
                        <div class="d-flex align-center">
                          <v-icon icon="mdi-puzzle-outline" color="primary" class="me-2" />
                          <div class="text-h6 font-weight-bold">
                            {{ plugin.display_name || name }}
                          </div>
                        </div>
                        <div class="d-flex align-center ga-2">
                          <v-chip
                            v-if="plugin.api_key_requirements && plugin.api_key_requirements.length > 0 && plugin.api_key_status"
                            :color="Object.values(plugin.api_key_status).every(status => status) ? 'success' : 'warning'"
                            size="small"
                            variant="tonal"
                            prepend-icon="mdi-key"
                          >
                            <v-tooltip activator="parent" location="bottom">
                              <template v-if="Object.values(plugin.api_key_status).every(status => status)">
                                All required API keys configured
                              </template>
                              <template v-else>
                                Missing API keys: {{ plugin.api_key_requirements.filter(p => !plugin.api_key_status[p]).join(', ') }}
                              </template>
                            </v-tooltip>
                            API Keys
                          </v-chip>
                          <v-chip
                            :color="plugin.enabled ? 'success' : 'error'"
                            size="small"
                            variant="tonal"
                          >
                            {{ plugin.enabled ? 'Enabled' : 'Disabled' }}
                          </v-chip>
                          <v-btn
                            :icon="expandedCards[name] ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                            variant="text"
                            size="small"
                            @click.stop="toggleCard(name)"
                          />
                        </div>
                      </div>

                      <!-- Plugin description preview -->
                      <div v-if="plugin.description && !expandedCards[name]" class="text-body-2 text-medium-emphasis mb-3">
                        {{ plugin.description.substring(0, 100) }}{{ plugin.description.length > 100 ? '...' : '' }}
                      </div>

                      <v-expand-transition>
                        <div v-if="expandedCards[name]" class="mt-4">

                          <!-- Parameters Section -->
                          <div v-if="plugin.parameters && Object.keys(plugin.parameters).length" class="mb-4">
                            <div class="d-flex flex-column ga-3" @click.stop>
                              <!-- Custom Plugin Parameter Component -->
                              <component
                                v-if="pluginParamComponents[name]"
                                :is="pluginParamComponents[name]"
                                :parameters="{ ...plugin.parameters, description: plugin.description }"
                                v-model="pluginParams[name]"
                              />

                              <!-- Default Parameter Rendering -->
                              <template v-else>
                                <div v-for="(param, paramName) in plugin.parameters" :key="paramName" class="mb-3">
                                  <!-- Boolean type - Switch -->
                                  <div v-if="param.type === 'boolean'">
                                    <v-switch
                                      v-model="pluginParams[name][paramName]"
                                      :label="paramName"
                                      :hint="param.description"
                                      persistent-hint
                                      color="primary"
                                      density="comfortable"
                                    />
                                  </div>

                                  <!-- List type -->
                                  <div v-else-if="param.type === 'list'">
                                    <v-combobox
                                      v-model="pluginParams[name][paramName]"
                                      :label="paramName"
                                      :placeholder="param.description"
                                      chips
                                      multiple
                                      variant="outlined"
                                      density="comfortable"
                                      @keydown.enter="handleEnterKey($event, name)"
                                    />
                                  </div>

                                  <!-- Default text/number field -->
                                  <div v-else>
                                    <v-text-field
                                      v-model="pluginParams[name][paramName]"
                                      :label="paramName"
                                      :type="param.type === 'number' || param.type === 'float' ? 'number' : 'text'"
                                      :placeholder="param.description"
                                      variant="outlined"
                                      density="comfortable"
                                      @keydown.enter="handleEnterKey($event, name)"
                                    />
                                  </div>
                                </div>
                              </template>
                            </div>
                          </div>

                          <!-- Execute Button -->
                          <v-btn
                            :loading="executing[name]"
                            :disabled="!plugin.enabled || executing[name] || (plugin.api_key_requirements && plugin.api_key_requirements.length > 0 && plugin.api_key_status && !Object.values(plugin.api_key_status).every(status => status))"
                            color="primary"
                            variant="flat"
                            block
                            class="mb-4"
                            prepend-icon="mdi-play"
                            @click.stop="executePlugin(name)"
                          >
                            <template v-if="plugin.api_key_requirements && plugin.api_key_requirements.length > 0 && plugin.api_key_status && !Object.values(plugin.api_key_status).every(status => status)">
                              API Key Required
                            </template>
                            <template v-else>
                              {{ executing[name] ? 'Executing...' : 'Execute Plugin' }}
                            </template>
                          </v-btn>

                          <!-- Results Available Indicator -->
                          <div v-if="results[name] || pluginErrors[name]" @click.stop class="mb-4">
                            <v-alert
                              v-if="pluginErrors[name]"
                              type="error"
                              variant="tonal"
                              density="compact"
                              :text="pluginErrors[name]"
                            />

                            <v-btn
                              v-else
                              variant="outlined"
                              color="success"
                              block
                              prepend-icon="mdi-eye"
                              @click="openResultsModal(name)"
                            >
                              View Results
                            </v-btn>
                          </div>
                        </div>
                      </v-expand-transition>
                    </v-card-text>
                  </v-card>
                </v-col>
              </v-row>

              <!-- Empty state -->
              <div v-else class="text-center pa-12">
                <v-icon
                  icon="mdi-puzzle-outline"
                  size="64"
                  color="grey-lighten-1"
                  class="mb-4"
                />
                <h3 class="text-h6 font-weight-medium mb-2">
                  No plugins available
                </h3>
                <p class="text-body-2 text-medium-emphasis mb-4">
                  Try selecting a different category or check your plugin configuration.
                </p>
                <v-btn
                  color="primary"
                  prepend-icon="mdi-refresh"
                  @click="loadPlugins"
                >
                  Refresh Plugins
                </v-btn>
              </div>
            </v-card-text>
          </v-card>
  </BaseDashboard>

  <!-- Results Modal -->
    <PluginResultsModal
      v-model="modalState.isOpen"
      :plugin-name="modalState.pluginName"
      :results="modalState.results"
      :error="modalState.error"
      :parameters="modalState.parameters"
      :execution-time="modalState.executionTime"
      @export="handleExportResults"
    />
</template>

<script setup>
import { ref, onMounted, reactive, computed, watch, markRaw } from 'vue'
import { pluginService } from '@/services/plugin'
import { usePluginApiKeys } from '@/composables/usePluginApiKeys'
import PluginResultsModal from '@/components/plugins/PluginResultsModal.vue'
import BaseDashboard from '@/components/BaseDashboard.vue'

const plugins = ref({})
const loading = ref(true)
const error = ref(null)
const expandedCards = ref({})
const executing = reactive({})
const results = reactive({})
const pluginParams = reactive({})
const pluginErrors = reactive({})
const pluginParamComponents = ref({})
const executionTimes = reactive({})

// Modal state
const modalState = reactive({
  isOpen: false,
  pluginName: '',
  results: null,
  error: null,
  parameters: {},
  executionTime: new Date()
})

const categories = ['Person', 'Network', 'Company', 'Other']
const selectedCategories = ref(['All'])

// Plugin API key checking
const { checkPluginApiKeys, getApiKeyWarningMessage } = usePluginApiKeys()

// Watch for changes in category selection to handle "All" logic
watch(selectedCategories, (newCategories, oldCategories) => {
  // If "All" was just selected
  if (newCategories.includes('All') && !oldCategories.includes('All')) {
    // Clear other selections and keep only "All"
    selectedCategories.value = ['All']
  }
  // If a specific category was selected while "All" was already selected
  else if (oldCategories.includes('All') && newCategories.length > 1) {
    // Remove "All" and keep only the newly selected categories
    selectedCategories.value = newCategories.filter(cat => cat !== 'All')
  }
  // If no categories are selected, default to "All"
  else if (newCategories.length === 0) {
    selectedCategories.value = ['All']
  }
}, { immediate: false })

const filteredPlugins = computed(() => {
  // If "All" is selected or no categories are selected, show all plugins
  if (selectedCategories.value.includes('All') || selectedCategories.value.length === 0) {
    return plugins.value
  }

  return Object.entries(plugins.value).reduce((acc, [name, plugin]) => {
    // Get the plugin's category, defaulting to 'Other' if not set or not matching predefined categories
    const pluginCategory = plugin.category && categories.includes(plugin.category) ? plugin.category : 'Other'
    // Include plugins that match any of the selected categories
    if (selectedCategories.value.includes(pluginCategory)) {
      acc[name] = plugin
    }
    return acc
  }, {})
})

const initializeExpandedState = (pluginsList) => {
  Object.keys(pluginsList).forEach(name => {
    expandedCards.value[name] = false
  })
}

const toggleCard = (name) => {
  expandedCards.value[name] = !expandedCards.value[name]
}

const loadPluginParamComponent = async (pluginName) => {
  const name = pluginName
    .replace(/Plugin$/, '') // Remove 'Plugin' suffix if present
    .replace(/^[a-z]/, c => c.toUpperCase()) // Ensure first letter is uppercase

  const componentName = `${name}PluginParams`

  try {
    const module = await import(`../components/plugins/${componentName}.vue`)
    pluginParamComponents.value[pluginName] = markRaw(module.default)
  } catch {
    // No custom parameter component found, use default rendering
    pluginParamComponents.value[pluginName] = null
  }
}

const loadPlugins = async () => {
  try {
    error.value = null
    plugins.value = await pluginService.listPlugins()
    initializeExpandedState(plugins.value)
    // Initialize parameters for each plugin and load custom parameter components
    const loadPromises = Object.keys(plugins.value).map(async (name) => {
      // Load custom parameter component
      await loadPluginParamComponent(name)

      // Initialize parameters
      pluginParams[name] = {}
      if (plugins.value[name].parameters) {
        Object.keys(plugins.value[name].parameters).forEach(paramName => {
          const param = plugins.value[name].parameters[paramName]
          // Set default value based on type
          if (param.type === 'boolean') {
            pluginParams[name][paramName] = param.default !== undefined ? param.default : true
          } else {
            pluginParams[name][paramName] = param.default || ''
          }
        })
      }
    })

    await Promise.all(loadPromises)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const executePlugin = async (name) => {
  // Check API key requirements first
  const plugin = plugins.value[name]
  if (plugin.api_key_requirements && plugin.api_key_requirements.length > 0) {
    const hasAllKeys = await checkPluginApiKeys(plugin)
    if (!hasAllKeys) {
      const warningMessage = getApiKeyWarningMessage(plugin)
      pluginErrors[name] = warningMessage
      return
    }
  }

  executing[name] = true
  pluginErrors[name] = null
  results[name] = null // Clear previous results
  executionTimes[name] = new Date() // Track execution time

  try {
    const result = await pluginService.executePlugin(name, pluginParams[name])

    // Handle async generator result
    if (result && typeof result[Symbol.asyncIterator] === 'function') {
      for await (const data of result) {
        try {
          results[name] = JSON.parse(data)
        } catch (parseError) {
          console.error('Failed to parse plugin response:', parseError)
          results[name] = data
        }
      }
    } else {
      results[name] = result
    }

    // Auto-open modal when execution completes
    if (results[name]) {
      openResultsModal(name)
    }

  } catch (err) {
    console.error('Plugin error:', err)
    pluginErrors[name] = err.message
  } finally {
    executing[name] = false
  }
}

const openResultsModal = (pluginName) => {
  modalState.pluginName = pluginName
  modalState.results = results[pluginName]
  modalState.error = pluginErrors[pluginName]
  modalState.parameters = { ...pluginParams[pluginName] }
  modalState.executionTime = executionTimes[pluginName] || new Date()
  modalState.isOpen = true
}

const handleExportResults = (exportData) => {
  // Create downloadable JSON file
  const dataStr = JSON.stringify(exportData, null, 2)
  const dataBlob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(dataBlob)

  const link = document.createElement('a')
  link.href = url
  link.download = `${exportData.pluginName}_results_${Date.now()}.json`
  link.click()

  URL.revokeObjectURL(url)
}

const handleEnterKey = (event, pluginName) => {
  if (plugins.value[pluginName].enabled && !executing[pluginName]) {
    event.preventDefault()
    executePlugin(pluginName)
  }
}

onMounted(() => {
  loadPlugins()
})
</script>

<style scoped>
</style>
