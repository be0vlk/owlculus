<template>
  <div class="d-flex flex-column ga-4">
    <!-- Status Messages -->
    <PluginStatusAlert
      v-for="(item, index) in statusMessages"
      :key="`status-${index}`"
      type="status"
      :message="item.data.message"
    />

    <!-- Shodan Results Grid -->
    <div v-if="shodanResults.length" class="shodan-results-grid">
      <v-row>
        <v-col
          v-for="(result, index) in shodanResults"
          :key="`shodan-${index}`"
          cols="12"
          lg="6"
          xl="4"
        >
          <v-card elevation="2" rounded="lg" class="h-100 host-card">
            <!-- Host Header -->
            <v-card-title class="d-flex align-center bg-primary-lighten-5">
              <v-icon icon="mdi-server-network" class="mr-3" />
              <div class="flex-grow-1">
                <div class="text-h6 d-flex align-center">
                  {{ result.ip }}
                  <v-btn
                    icon="mdi-content-copy"
                    size="x-small"
                    variant="text"
                    @click="copyToClipboard(result.ip)"
                    class="ml-2"
                  >
                    <v-tooltip activator="parent" location="top">Copy IP</v-tooltip>
                  </v-btn>
                </div>
                <div class="text-caption text-medium-emphasis">
                  {{ result.organization || 'Unknown Organization' }}
                </div>
              </div>
            </v-card-title>

            <v-card-text class="pa-0">
              <!-- Host Information -->
              <div class="pa-4">
                <!-- Location -->
                <div v-if="result.country || result.city" class="mb-3">
                  <div class="d-flex align-center mb-1">
                    <v-icon icon="mdi-map-marker" size="small" class="mr-2" />
                    <span class="text-subtitle2">Location</span>
                  </div>
                  <div class="text-body-2">
                    {{ [result.city, result.country].filter(Boolean).join(', ') || 'Unknown' }}
                  </div>
                </div>

                <!-- Hostnames -->
                <div v-if="result.hostnames && result.hostnames.length" class="mb-3">
                  <div class="d-flex align-center mb-1">
                    <v-icon icon="mdi-web" size="small" class="mr-2" />
                    <span class="text-subtitle2">Hostnames</span>
                  </div>
                  <div class="d-flex flex-wrap ga-1">
                    <v-chip
                      v-for="hostname in result.hostnames.slice(0, 3)"
                      :key="hostname"
                      size="small"
                      variant="outlined"
                      color="info"
                      @click="copyToClipboard(hostname)"
                      class="cursor-pointer"
                    >
                      {{ hostname }}
                      <v-tooltip activator="parent" location="top">Click to copy</v-tooltip>
                    </v-chip>
                    <v-chip
                      v-if="result.hostnames.length > 3"
                      size="small"
                      variant="text"
                      color="grey"
                    >
                      +{{ result.hostnames.length - 3 }} more
                    </v-chip>
                  </div>
                </div>

                <!-- Ports (for host lookup results) -->
                <div v-if="result.ports && result.ports.length" class="mb-3">
                  <div class="d-flex align-center mb-1">
                    <v-icon icon="mdi-ethernet" size="small" class="mr-2" />
                    <span class="text-subtitle2">Open Ports ({{ result.ports.length }})</span>
                  </div>
                  <div class="d-flex flex-wrap ga-1">
                    <v-chip
                      v-for="port in result.ports.slice(0, 10)"
                      :key="port"
                      size="small"
                      variant="outlined"
                      color="success"
                    >
                      {{ port }}
                    </v-chip>
                    <v-chip
                      v-if="result.ports.length > 10"
                      size="small"
                      variant="text"
                      color="grey"
                    >
                      +{{ result.ports.length - 10 }} more
                    </v-chip>
                  </div>
                </div>

                <!-- Single Service (for search results) -->
                <div v-if="result.port && result.search_type !== 'host_lookup'" class="mb-3">
                  <div class="d-flex align-center mb-1">
                    <v-icon icon="mdi-ethernet" size="small" class="mr-2" />
                    <span class="text-subtitle2">Service</span>
                  </div>
                  <v-chip class="mr-2" color="success" size="small" variant="outlined">
                    {{ result.port }}/{{ result.transport || 'tcp' }}
                  </v-chip>
                  <span class="text-body-2">{{ result.service || 'Unknown' }}</span>
                  <span v-if="result.version" class="text-caption text-medium-emphasis ml-1">
                    ({{ result.version }})
                  </span>
                </div>

                <!-- Vulnerabilities -->
                <div v-if="result.vulns && result.vulns.length" class="mb-3">
                  <div class="d-flex align-center mb-1">
                    <v-icon icon="mdi-shield-alert" size="small" class="mr-2" color="error" />
                    <span class="text-subtitle2">Vulnerabilities ({{ result.vulns.length }})</span>
                  </div>
                  <div class="d-flex flex-wrap ga-1">
                    <v-chip
                      v-for="vuln in result.vulns.slice(0, 3)"
                      :key="vuln"
                      size="small"
                      variant="outlined"
                      color="error"
                    >
                      {{ vuln }}
                    </v-chip>
                    <v-chip v-if="result.vulns.length > 3" color="grey" size="small" variant="text">
                      +{{ result.vulns.length - 3 }} more
                    </v-chip>
                  </div>
                </div>

                <!-- Services (for host lookup results) -->
                <div v-if="result.services && result.services.length" class="mb-3">
                  <div class="d-flex align-center mb-2">
                    <v-icon icon="mdi-application-cog" size="small" class="mr-2" />
                    <span class="text-subtitle2">Services ({{ result.services.length }})</span>
                  </div>

                  <v-expansion-panels variant="accordion" multiple>
                    <v-expansion-panel
                      v-for="(service, sIndex) in result.services.slice(0, 5)"
                      :key="`service-${sIndex}`"
                      elevation="0"
                    >
                      <v-expansion-panel-title class="py-2">
                        <div class="d-flex align-center">
                          <v-chip size="x-small" variant="outlined" color="primary" class="mr-2">
                            {{ service.port }}/{{ service.transport }}
                          </v-chip>
                          <span class="text-body-2">{{ service.service }}</span>
                          <span
                            v-if="service.version"
                            class="text-caption text-medium-emphasis ml-2"
                          >
                            v{{ service.version }}
                          </span>
                        </div>
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <div v-if="service.banner" class="service-banner">
                          <div class="text-caption text-medium-emphasis mb-1">Service Banner:</div>
                          <pre class="text-body-2 font-mono">{{ service.banner }}</pre>
                        </div>
                      </v-expansion-panel-text>
                    </v-expansion-panel>
                  </v-expansion-panels>

                  <div
                    v-if="result.services.length > 5"
                    class="text-caption text-center mt-2 text-medium-emphasis"
                  >
                    Showing 5 of {{ result.services.length }} services
                  </div>
                </div>

                <!-- Service Banner (for individual search results) -->
                <div v-if="result.banner && result.search_type !== 'host_lookup'" class="mb-3">
                  <div class="d-flex align-center mb-1">
                    <v-icon icon="mdi-code-braces" size="small" class="mr-2" />
                    <span class="text-subtitle2">Service Banner</span>
                  </div>
                  <v-card elevation="1" rounded="lg" color="grey-lighten-5">
                    <v-card-text class="pa-3">
                      <div class="d-flex justify-space-between align-start">
                        <pre class="text-body-2 font-mono flex-grow-1 service-banner">{{
                          result.banner
                        }}</pre>
                        <v-btn
                          icon="mdi-content-copy"
                          size="small"
                          variant="text"
                          @click="copyToClipboard(result.banner)"
                          class="ml-3 flex-shrink-0"
                        >
                          <v-tooltip activator="parent" location="top">Copy banner</v-tooltip>
                        </v-btn>
                      </div>
                    </v-card-text>
                  </v-card>
                </div>

                <!-- Last Update -->
                <div v-if="result.last_update" class="text-caption text-medium-emphasis">
                  <v-icon icon="mdi-clock-outline" size="x-small" class="mr-1" />
                  Last updated: {{ formatDate(result.last_update) }}
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </div>

    <!-- Error Messages -->
    <PluginStatusAlert
      v-for="(item, index) in errorMessages"
      :key="`error-${index}`"
      type="error"
      :message="item.data.message"
      plugin-name="Shodan Search"
    />

    <!-- No Results -->
    <NoResultsCard v-if="!parsedResults.length" />
  </div>
</template>

<script setup>
import { computed, toRef } from 'vue'
import { usePluginResults } from '@/composables/usePluginResults'
import PluginStatusAlert from './PluginStatusAlert.vue'
import NoResultsCard from './NoResultsCard.vue'

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  },
})

const { parsedResults, statusMessages, errorMessages } = usePluginResults(toRef(props, 'result'))

// Extract Shodan data results
const shodanResults = computed(() => {
  return parsedResults.value.filter((item) => item.type === 'data').map((item) => item.data)
})

const formatDate = (dateString) => {
  if (!dateString || dateString === 'Unknown') return 'Unknown'

  try {
    // Handle timestamp format
    if (typeof dateString === 'string' && dateString.includes('T')) {
      return new Date(dateString).toLocaleDateString()
    }

    // Handle other formats
    return new Date(dateString).toLocaleDateString()
  } catch {
    return dateString
  }
}

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}
</script>

<style scoped>
.host-card {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.host-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgb(0 0 0 / 12%);
}

.service-banner {
  max-height: 150px;
  overflow-y: auto;
  background: rgb(var(--v-theme-surface), 0.7);
  border-radius: 4px;
  padding: 8px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.shodan-results-grid {
  margin-top: 1.5rem;
}

.bg-primary-lighten-5 {
  background: linear-gradient(
    45deg,
    rgb(var(--v-theme-primary), 0.08),
    rgb(var(--v-theme-primary), 0.03)
  );
}

.cursor-pointer {
  cursor: pointer;
}

/* Enhanced chip styles */
.v-chip[color='success'] {
  background: rgb(var(--v-theme-success), 0.12);
  border: 1px solid rgb(var(--v-theme-success), 0.3);
}

.v-chip[color='error'] {
  background: rgb(var(--v-theme-error), 0.12);
  border: 1px solid rgb(var(--v-theme-error), 0.3);
}

.v-chip[color='info'] {
  background: rgb(var(--v-theme-info), 0.12);
  border: 1px solid rgb(var(--v-theme-info), 0.3);
}
</style>
