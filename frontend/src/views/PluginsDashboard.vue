<template>
  <div class="min-h-screen bg-gray-100 dark:bg-gray-900">
    <div class="flex">
      <!-- Sidebar -->
      <Sidebar class="fixed inset-y-0 left-0" />

      <!-- Main content -->
      <div class="flex-1 ml-64">
        <header class="bg-white shadow dark:bg-gray-800">
          <div class="max-w-7xl mx-auto px-8 py-6">
            <h1 class="text-3xl font-bold text-gray-900 dark:text-gray-100">Plugins Dashboard</h1>
          </div>
        </header>
        <main class="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
          <div v-if="error" class="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-400 dark:border-red-500 p-4 mb-4">
            {{ error }}
          </div>
          
          <div v-if="loading" class="flex justify-center items-center h-64">
            <LoadingSpinner />
          </div>
          
          <div v-else>
            <!-- Tab Navigation -->
            <div class="border-b border-gray-200 dark:border-gray-700 mb-6">
              <nav class="-mb-px flex space-x-8" aria-label="Plugin Categories">
                <button
                  v-for="category in categories"
                  :key="category"
                  @click="currentCategory = category"
                  class="py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap"
                  :class="[
                    currentCategory === category
                      ? 'border-cyan-500 text-cyan-600 dark:border-cyan-400 dark:text-cyan-400'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                  ]"
                >
                  {{ category }}
                </button>
              </nav>
            </div>

            <!-- Plugin Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div v-for="(plugin, name) in filteredPlugins" :key="name" 
                   class="bg-white dark:bg-gray-800 shadow-sm rounded-lg border border-gray-200 dark:border-gray-700 flex flex-col cursor-pointer transition-all duration-200"
                   :class="expandedCards[name] ? 'h-full' : 'h-40'"
                   @click="toggleCard(name)">
                <div class="p-4 flex-1 overflow-hidden">
                  <div class="flex justify-between items-start">
                    <h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100">{{ plugin.display_name || name }}</h2>
                    <div class="flex items-center">
                      <span class="px-2 py-1 text-xs rounded-full" 
                            :class="plugin.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'">
                        {{ plugin.enabled ? 'Enabled' : 'Disabled' }}
                      </span>
                      <button @click.stop="toggleCard(name)" 
                              class="ml-2 p-1 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 transition-colors rounded-full hover:bg-gray-100 dark:hover:bg-gray-700">
                        <svg v-if="expandedCards[name]" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                          <path fill-rule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clip-rule="evenodd" />
                        </svg>
                        <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                          <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  
                  <p class="text-gray-600 dark:text-gray-300 mt-2" :class="{'line-clamp-2': !expandedCards[name]}">
                    {{ plugin.description }}
                  </p>

                  <div v-if="expandedCards[name]" 
                       class="mt-6 space-y-6 animate-fade-in">
                    <div v-if="plugin.parameters && Object.keys(plugin.parameters).length">
                      <h3 class="font-medium text-gray-900 dark:text-gray-100">Parameters</h3>
                      <div class="mt-3 space-y-3" @click.stop>
                        <div v-for="(param, paramName) in plugin.parameters" :key="paramName">
                          <BaseInput 
                            v-if="param.type !== 'list'"
                            :id="paramName"
                            v-model="pluginParams[name][paramName]"
                            :type="param.type === 'number' ? 'number' : 'text'"
                            :placeholder="param.description"
                            :label="paramName"
                            class="bg-gray-50 dark:bg-gray-700/50"
                            @keydown.enter="handleEnterKey($event, name)"
                          />
                          <BaseListInput
                            v-else
                            :id="paramName"
                            v-model="pluginParams[name][paramName]"
                            :placeholder="param.description"
                            :label="paramName"
                            class="bg-gray-50 dark:bg-gray-700/50"
                            @keydown.enter="handleEnterKey($event, name)"
                          />
                        </div>
                      </div>
                    </div>

                    <button 
                      @click.stop="executePlugin(name)"
                      :disabled="!plugin.enabled || executing[name]"
                      class="w-full px-4 py-2 bg-cyan-600 text-white rounded-md hover:bg-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors"
                    >
                      <span v-if="executing[name]" class="flex items-center justify-center">
                        <LoadingSpinner class="h-4 w-4 mr-2" />
                        Executing...
                      </span>
                      <span v-else>Execute Plugin</span>
                    </button>

                    <div v-if="results[name]" @click.stop>
                      <h3 class="font-medium text-lg mb-4">Results</h3>
                      <PluginResult 
                        :result="results[name]" 
                        :plugin-name="name"
                      />
                    </div>
                    
                    <div v-if="pluginErrors[name]" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded" @click.stop>
                      {{ pluginErrors[name] }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import { pluginService } from '@/services/plugin'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import BaseInput from '@/components/BaseInput.vue'
import BaseListInput from '@/components/BaseListInput.vue'
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
    const plugin = plugins.value[name]
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

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.2s ease-in-out;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>