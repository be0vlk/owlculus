<template>
  <BaseDashboard :error="error" :loading="loading" title="Plugins">
    <template #loading>
      <v-card variant="outlined">
        <v-card-title class="d-flex flex-wrap ga-2 align-center pa-4 bg-surface text-wrap">
          <v-skeleton-loader type="text" width="200" />
          <v-spacer />
          <v-skeleton-loader type="button" width="120" />
        </v-card-title>
        <v-divider />
        <v-card-text class="text-center pa-16">
          <v-progress-circular color="primary" indeterminate size="64" width="4" />
          <div class="text-title-large mt-4">Loading plugins...</div>
        </v-card-text>
      </v-card>
    </template>

    <!-- Main Content -->
    <!-- Plugin Management Card -->
    <v-card variant="outlined">
      <!-- Header -->
      <v-card-title class="d-flex flex-wrap ga-2 align-center pa-4 bg-surface text-wrap">
        <v-icon class="me-3" color="primary" icon="mdi-tools" size="large" />
        <div class="flex-grow-1">
          <div class="text-title-large font-weight-bold">Plugin Management</div>
          <div class="text-body-medium text-medium-emphasis">
            Execute OSINT plugins and analyze results
          </div>
        </div>
        <div class="d-flex align-center ga-2">
          <v-tooltip location="bottom" text="Refresh plugins list">
            <template #activator="{ props }">
              <v-btn
                size="small"
                :loading="loading"
                icon="mdi-refresh"
                aria-label="Refresh plugins"
                v-bind="props"
                variant="outlined"
                @click="loadPlugins"
              />
            </template>
          </v-tooltip>
        </div>
      </v-card-title>

      <v-divider />

      <!-- Category Tabs -->
      <v-tabs v-model="selectedTab" align-tabs="start" class="border-b" color="primary">
        <v-tab value="all">
          <v-icon class="me-2" icon="mdi-view-grid" />
          All Plugins
        </v-tab>
        <v-tab v-for="category in categories" :key="category" :value="category.toLowerCase()">
          <v-icon :icon="getCategoryIcon(category)" class="me-2" />
          {{ category }}
        </v-tab>
      </v-tabs>

      <!-- Plugin Grid -->
      <v-card-text class="pa-4">
        <v-row v-if="Object.keys(filteredPlugins).length">
          <v-col v-for="(plugin, name) in filteredPlugins" :key="name" cols="12" lg="4" md="6">
            <v-card :class="{ 'h-100': expandedCards[name] }" :ripple="false" variant="outlined">
              <v-card-text class="pa-4">
                <div class="d-flex flex-wrap ga-2 justify-space-between align-start mb-3">
                  <div class="d-flex align-center">
                    <v-icon class="me-2" color="primary" icon="mdi-puzzle-outline" />
                    <div class="text-title-large font-weight-bold">
                      {{ plugin.display_name || name }}
                    </div>
                  </div>
                  <div class="d-flex align-center ga-2">
                    <v-chip
                      v-if="plugin.api_key_requirements?.length && plugin.api_key_status"
                      :color="missingKeys(plugin).length ? 'warning' : 'success'"
                      prepend-icon="mdi-key"
                      size="small"
                      variant="tonal"
                    >
                      <v-tooltip activator="parent" location="bottom">
                        <template v-if="missingKeys(plugin).length">
                          Missing API keys: {{ missingKeys(plugin).join(', ') }}
                        </template>
                        <template v-else>All required API keys configured</template>
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
                      :aria-label="`${expandedCards[name] ? 'Collapse' : 'Configure'} ${plugin.display_name || name}`"
                      :aria-expanded="!!expandedCards[name]"
                      :icon="expandedCards[name] ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                      size="small"
                      variant="text"
                      @click.stop="toggleCard(name)"
                    />
                  </div>
                </div>

                <!-- Plugin description preview -->
                <div
                  v-if="plugin.description && !expandedCards[name]"
                  class="text-body-medium text-medium-emphasis mb-3"
                >
                  {{ plugin.description.substring(0, 100)
                  }}{{ plugin.description.length > 100 ? '...' : '' }}
                </div>

                <v-expand-transition>
                  <v-form
                    v-if="expandedCards[name]"
                    :ref="(form) => (pluginForms[name] = form)"
                    class="mt-4"
                    :disabled="executing[name] || !plugin.enabled"
                    @submit.prevent="executePlugin(name)"
                  >
                    <ApiKeyWarning
                      v-if="missingKeys(plugin).length"
                      :missing-providers="missingKeys(plugin)"
                    />

                    <!-- Parameters Section -->
                    <div
                      v-if="plugin.parameters && Object.keys(plugin.parameters).length"
                      class="mb-4"
                    >
                      <div class="d-flex flex-column ga-3" @click.stop>
                        <!-- Custom Plugin Parameter Component -->
                        <component
                          :is="pluginParamComponents[name]"
                          v-if="pluginParamComponents[name]"
                          v-model="pluginParams[name]"
                          :parameters="{ ...plugin.parameters, description: plugin.description }"
                        />

                        <!-- Default Parameter Rendering -->
                        <GenericPluginParams
                          v-else
                          v-model="pluginParams[name]"
                          :parameters="plugin.parameters"
                        />
                      </div>
                    </div>

                    <!-- Execute Button -->
                    <v-btn
                      :disabled="
                        !activeCase.ready ||
                        !activeCase.activeCaseId ||
                        !plugin.enabled ||
                        executing[name] ||
                        missingKeys(plugin).length > 0
                      "
                      :loading="executing[name]"
                      block
                      class="mb-4"
                      color="primary"
                      prepend-icon="mdi-play"
                      variant="flat"
                      type="submit"
                    >
                      <template v-if="missingKeys(plugin).length">API Key Required</template>
                      <template v-else>
                        {{ executing[name] ? 'Executing...' : 'Execute Plugin' }}
                      </template>
                    </v-btn>

                    <!-- Results Available Indicator -->
                    <div v-if="pluginErrors[name]" class="mb-4" @click.stop>
                      <v-alert
                        v-if="pluginErrors[name]"
                        :text="pluginErrors[name]"
                        density="compact"
                        type="error"
                        variant="tonal"
                      />
                    </div>
                  </v-form>
                </v-expand-transition>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- Empty state -->
        <div v-else class="text-center pa-12">
          <v-icon class="mb-4" color="grey-lighten-1" icon="mdi-puzzle-outline" size="64" />
          <h3 class="text-title-large font-weight-medium mb-2">No plugins available</h3>
          <p class="text-body-medium text-medium-emphasis mb-4">
            Try selecting a different category or check your plugin configuration.
          </p>
          <v-btn color="primary" prepend-icon="mdi-refresh" @click="loadPlugins">
            Refresh Plugins
          </v-btn>
        </div>
      </v-card-text>
    </v-card>
    <PluginExecutionHistory
      v-if="activeCase.activeCaseId"
      :case-id="activeCase.activeCaseId"
      :execution-id="acceptedExecutionId"
    />
  </BaseDashboard>
</template>

<script setup>
import { useActiveCaseStore } from '@/stores/activeCase'
import PluginExecutionHistory from '@/components/plugins/PluginExecutionHistory.vue'
import GenericPluginParams from '@/components/plugins/GenericPluginParams.vue'
import { ref, onMounted, reactive, computed, markRaw } from 'vue'
import { pluginService } from '@/services/plugin'
import ApiKeyWarning from '@/components/plugins/ApiKeyWarning.vue'
import BaseDashboard from '@/components/BaseDashboard.vue'

const acceptedExecutionId = ref(null)
const activeCase = useActiveCaseStore()
const plugins = ref({})
const loading = ref(true)
const error = ref(null)
const expandedCards = ref({})
const executing = reactive({})
const pluginParams = reactive({})
const pluginErrors = reactive({})
const pluginParamComponents = ref({})

const categories = ['Person', 'Network', 'Company', 'Other']
const selectedTab = ref('all')

const missingKeys = (plugin) =>
  plugin.api_key_status
    ? (plugin.api_key_requirements ?? []).filter((provider) => !plugin.api_key_status[provider])
    : []

// Helper function to get category icons
const getCategoryIcon = (category) => {
  const iconMap = {
    Person: 'mdi-account',
    Network: 'mdi-lan',
    Company: 'mdi-domain',
    Other: 'mdi-puzzle',
  }
  return iconMap[category] || 'mdi-puzzle'
}

const filteredPlugins = computed(() =>
  Object.fromEntries(
    Object.entries(plugins.value)
      .filter(
        ([, plugin]) =>
          selectedTab.value === 'all' ||
          (categories.includes(plugin.category) ? plugin.category : 'Other').toLowerCase() ===
            selectedTab.value,
      )
      .toSorted(([nameA, a], [nameB, b]) =>
        (a.display_name || nameA).localeCompare(b.display_name || nameB),
      ),
  ),
)

const toggleCard = (name) => {
  expandedCards.value[name] = !expandedCards.value[name]
}

const loadPluginParamComponent = async (pluginName) => {
  const name = pluginName
    .replace(/Plugin$/, '') // Remove 'Plugin' suffix if present
    .replace(/^[a-z]/, (c) => c.toUpperCase()) // Ensure first letter is uppercase

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
    // Initialize parameters for each plugin and load custom parameter components
    const loadPromises = Object.keys(plugins.value).map(async (name) => {
      // Load custom parameter component
      await loadPluginParamComponent(name)

      // Initialize parameters
      pluginParams[name] = {}
      if (plugins.value[name].parameters) {
        Object.keys(plugins.value[name].parameters).forEach((paramName) => {
          if (paramName === 'case_id') return
          const param = plugins.value[name].parameters[paramName]
          // Set default value based on type
          if (param.type === 'boolean') {
            pluginParams[name][paramName] = param.default !== undefined ? param.default : true
          } else {
            pluginParams[name][paramName] = param.default ?? (param.type === 'list' ? [] : '')
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

const pluginForms = {}

const executePlugin = async (name) => {
  const caseId = activeCase.activeCaseId
  const plugin = plugins.value[name]
  if (!activeCase.ready || !caseId || !plugin.enabled || executing[name]) return
  if (missingKeys(plugin).length) return
  if (pluginForms[name] && !(await pluginForms[name].validate()).valid) return
  if (!activeCase.ready || activeCase.activeCaseId !== caseId) return
  executing[name] = true
  pluginErrors[name] = null

  try {
    const accepted = await pluginService.executePlugin(name, pluginParams[name], caseId)
    if (activeCase.activeCaseId === caseId) acceptedExecutionId.value = accepted.id
  } catch (err) {
    console.error('Plugin error:', err)
    pluginErrors[name] = err.message
  } finally {
    executing[name] = false
  }
}

onMounted(() => {
  loadPlugins()
})
</script>
