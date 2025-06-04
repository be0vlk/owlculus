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
                  
                  <v-card-text class="pa-0">
                    <p class="text-body-2" :class="{'text-truncate': !expandedCards[name]}">
                      {{ plugin.description }}
                    </p>
                  </v-card-text>

                  <v-expand-transition>
                    <div v-if="expandedCards[name]" class="mt-6">
                      <!-- Parameters Section -->
                      <div v-if="plugin.parameters && Object.keys(plugin.parameters).length" class="mb-4">
                        <v-card-subtitle class="pa-0 text-h6 mb-3">Parameters</v-card-subtitle>
                        <div class="d-flex flex-column ga-3" @click.stop>
                          <div v-for="(param, paramName) in plugin.parameters" :key="paramName" class="mb-3">
                            <div v-if="param.type !== 'list'">
                              <v-text-field
                                v-model="pluginParams[name][paramName]"
                                :label="paramName"
                                :type="param.type === 'number' ? 'number' : 'text'"
                                :placeholder="param.description"
                                variant="outlined"
                                density="compact"
                                @keydown.enter="handleEnterKey($event, name)"
                              />
                            </div>
                            <div v-else>
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
                          </div>
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

                      <!-- Results Section -->
                      <div v-if="results[name]" @click.stop class="mb-4">
                        <v-card-subtitle class="pa-0 text-h6 mb-3">Results</v-card-subtitle>
                        <PluginResult 
                          :result="results[name]" 
                          :plugin-name="name"
                        />
                      </div>
                      
                      <!-- Error Section -->
                      <v-alert
                        v-if="pluginErrors[name]"
                        type="error"
                        :text="pluginErrors[name]"
                        @click.stop
                      />
                    </div>
                  </v-expand-transition>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </div>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import { pluginService } from '@/services/plugin'
import PluginResult from '@/components/PluginResult.vue'
import Sidebar from '@/components/Sidebar.vue'

const plugins = ref({})
const loading = ref(true)
const error = ref(null)
const expandedCards = ref({})
const executing = reactive({})
const results = reactive({})
const pluginParams = reactive({})
const pluginErrors = reactive({})

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

const loadPlugins = async () => {
  try {
    error.value = null
    plugins.value = await pluginService.listPlugins()
    initializeExpandedState(plugins.value)
    // Initialize parameters for each plugin
    Object.keys(plugins.value).forEach(name => {
      pluginParams[name] = {}
      if (plugins.value[name].parameters) {
        Object.keys(plugins.value[name].parameters).forEach(paramName => {
          pluginParams[name][paramName] = plugins.value[name].parameters[paramName].default || ''
        })
      }
    })
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
    
  } catch (e) {
    console.error('Plugin error:', e)
    pluginErrors[name] = e.message
  } finally {
    executing[name] = false
  }
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