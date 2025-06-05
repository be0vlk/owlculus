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
                Plugins Dashboard
              </h1>
            </v-col>
          </v-row>
        </div>

        <!-- Error state -->
        <v-alert
          v-if="error"
          type="error"
          class="ma-4"
          :text="error"
          prominent
          border="start"
        />
        
        <!-- Loading state -->
        <v-card-text v-if="loading" class="text-center pa-16">
          <v-progress-circular
            size="64"
            width="4"
            color="primary"
            indeterminate
          />
          <v-card-text class="text-h6 mt-4">Loading plugins...</v-card-text>
        </v-card-text>
        
        <div v-else>
          <!-- Tab Navigation -->
          <v-tabs
            v-model="currentCategory"
            class="mb-6"
            color="primary"
          >
            <v-tab
              v-for="category in categories"
              :key="category"
              :value="category"
            >
              {{ category }}
            </v-tab>
          </v-tabs>

          <!-- Plugin Grid -->
          <v-row>
            <v-col 
              v-for="(plugin, name) in filteredPlugins" 
              :key="name"
              cols="12" 
              md="6" 
              lg="4"
            >
              <v-card 
                :class="{ 'h-100': expandedCards[name] }"
                :ripple="false"
                @click="toggleCard(name)"
                style="cursor: pointer;"
              >
                <v-card-text>
                  <div class="d-flex justify-space-between align-start mb-3">
                    <v-card-title class="pa-0 text-h6">
                      {{ plugin.display_name || name }}
                    </v-card-title>
                    <div class="d-flex align-center ga-2">
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
                  
                  <!-- Description removed from preview - now shown in parameter component -->

                  <v-expand-transition>
                    <div v-if="expandedCards[name]" class="mt-6">
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
                                  density="compact"
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
                                  density="compact"
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
                                  density="compact"
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
                        :disabled="!plugin.enabled || executing[name]"
                        color="primary"
                        block
                        class="mb-4"
                        @click.stop="executePlugin(name)"
                      >
                        {{ executing[name] ? 'Executing...' : 'Execute Plugin' }}
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
        </div>
      </v-container>
    </v-main>

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
  </v-app>
</template>

<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import { pluginService } from '@/services/plugin'
import PluginResultsModal from '@/components/PluginResultsModal.vue'
import Sidebar from '@/components/Sidebar.vue'

const plugins = ref({})
const loading = ref(true)
const error = ref(null)
const expandedCards = ref({})
const executing = reactive({})
const results = reactive({})
const pluginParams = reactive({})
const pluginErrors = reactive({})
const pluginParamComponents = reactive({})
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
const currentCategory = ref('Person')

const filteredPlugins = computed(() => {
  return Object.entries(plugins.value).reduce((acc, [name, plugin]) => {
    // Get the plugin's category, defaulting to 'Other' if not set or not matching predefined categories
    const pluginCategory = plugin.category && categories.includes(plugin.category) ? plugin.category : 'Other'
    // Only include plugins that match the current category
    if (pluginCategory === currentCategory.value) {
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
    const module = await import(`@/components/plugins/${componentName}.vue`)
    pluginParamComponents[pluginName] = module.default
  } catch (error) {
    // No custom parameter component found, use default rendering
    pluginParamComponents[pluginName] = null
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