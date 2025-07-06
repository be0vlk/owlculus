<template>
  <div class="d-flex flex-column ga-4">
    <!-- Status Messages -->
    <PluginStatusAlert
      v-for="(item, index) in statusMessages"
      :key="`status-${index}`"
      type="status"
      :message="item.data.status"
    />

    <!-- Summary Card -->
    <v-card v-if="summaryData" elevation="3" rounded="lg" class="summary-card">
      <v-card-title class="bg-gradient-primary">
        <v-icon icon="mdi-chart-donut" class="mr-3" />
        Subdomain Enumeration Summary
      </v-card-title>
      <v-card-text class="pa-4">
        <v-row>
          <v-col cols="12" md="4">
            <div class="text-center">
              <div class="text-h2 font-weight-bold text-primary">
                {{ summaryData.total_discovered }}
              </div>
              <div class="text-subtitle-2 text-medium-emphasis">Subdomains Discovered</div>
            </div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-center">
              <div class="text-h2 font-weight-bold text-success">
                {{ summaryData.total_resolved }}
              </div>
              <div class="text-subtitle-2 text-medium-emphasis">Successfully Resolved</div>
            </div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-center">
              <div class="text-h2 font-weight-bold text-warning">
                {{
                  Math.round((summaryData.total_resolved / summaryData.total_discovered) * 100) ||
                  0
                }}%
              </div>
              <div class="text-subtitle-2 text-medium-emphasis">Resolution Rate</div>
            </div>
          </v-col>
        </v-row>

        <v-divider class="my-4" />

        <div class="d-flex align-center justify-center flex-wrap ga-2">
          <div class="text-subtitle-2 text-medium-emphasis mr-2">Sources Used:</div>
          <v-chip
            v-for="source in summaryData.sources_used"
            :key="source"
            size="small"
            :color="getSourceColor(source)"
            variant="tonal"
          >
            <v-icon start size="small">{{ getSourceIcon(source) }}</v-icon>
            {{ source }}
          </v-chip>
        </div>
      </v-card-text>
    </v-card>

    <!-- Subdomain Results Grid -->
    <div v-if="subdomainResults.length" class="subdomain-results-grid">
      <v-row>
        <v-col
          v-for="(subdomain, index) in sortedSubdomains"
          :key="`subdomain-${index}`"
          cols="12"
          md="6"
          lg="4"
        >
          <v-card elevation="2" rounded="lg" class="h-100 subdomain-card">
            <v-card-title class="d-flex align-center pa-3 bg-primary-lighten-5">
              <v-icon
                :icon="subdomain.resolved ? 'mdi-check-circle' : 'mdi-subdirectory-arrow-right'"
                :color="subdomain.resolved ? 'success' : 'grey'"
                class="mr-2"
                size="small"
              />
              <div class="flex-grow-1 text-truncate">
                <div class="text-body-1 font-weight-medium text-truncate">
                  {{ subdomain.subdomain }}
                </div>
              </div>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(subdomain.subdomain)"
              >
                <v-tooltip activator="parent" location="top">Copy subdomain</v-tooltip>
              </v-btn>
            </v-card-title>

            <v-card-text class="pa-3">
              <!-- IP Address -->
              <div v-if="subdomain.ip" class="d-flex align-center mb-2">
                <v-icon icon="mdi-ip-network" size="small" class="mr-2" color="success" />
                <code class="text-body-2 flex-grow-1">{{ subdomain.ip }}</code>
                <v-btn
                  icon="mdi-content-copy"
                  size="x-small"
                  variant="text"
                  @click="copyToClipboard(subdomain.ip)"
                >
                  <v-tooltip activator="parent" location="top">Copy IP</v-tooltip>
                </v-btn>
              </div>

              <!-- Sources -->
              <div class="d-flex align-center flex-wrap ga-1">
                <v-icon icon="mdi-source-merge" size="small" class="mr-1" />
                <v-chip
                  v-for="source in subdomain.source.split(', ')"
                  :key="source"
                  size="x-small"
                  :color="getSourceColor(source)"
                  variant="tonal"
                  class="ma-0"
                >
                  {{ source }}
                </v-chip>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Export Actions -->
      <div class="d-flex justify-center mt-4 ga-2">
        <v-btn variant="outlined" @click="copyAllSubdomains">
          <v-icon start>mdi-content-copy</v-icon>
          Copy All Subdomains
        </v-btn>

        <v-btn variant="outlined" @click="copyResolvedOnly">
          <v-icon start>mdi-check-all</v-icon>
          Copy Resolved Only
        </v-btn>

        <v-btn variant="outlined" @click="copyAsHostsFile">
          <v-icon start>mdi-file-document</v-icon>
          Copy as Hosts File
        </v-btn>
      </div>
    </div>

    <!-- Completion Messages -->
    <PluginStatusAlert
      v-for="(item, index) in completionMessages"
      :key="`complete-${index}`"
      type="complete"
      :message="'Subdomain enumeration completed successfully'"
      plugin-name="Subdomain Enumeration"
    />

    <!-- Error Messages -->
    <PluginStatusAlert
      v-for="(item, index) in errorMessages"
      :key="`error-${index}`"
      type="error"
      :message="item.data.message"
      plugin-name="Subdomain Enumeration"
    />

    <!-- No Results -->
    <NoResultsCard v-if="!hasResults && !statusMessages.length" />
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

const { statusMessages, completionMessages, errorMessages, dataResults } = usePluginResults(
  toRef(props, 'result'),
)

// Extract subdomain results
const subdomainResults = computed(() => {
  return dataResults.value.filter(
    (item) => item.data.subdomain && item.data.subdomain !== undefined,
  )
})

// Extract summary data
const summaryData = computed(() => {
  const summary = dataResults.value.find((item) => item.data.phase === 'summary')
  return summary ? summary.data : null
})

// Sort subdomains: resolved first, then alphabetically
const sortedSubdomains = computed(() => {
  return [...subdomainResults.value]
    .map((item) => item.data)
    .sort((a, b) => {
      if (a.resolved && !b.resolved) return -1
      if (!a.resolved && b.resolved) return 1
      return a.subdomain.localeCompare(b.subdomain)
    })
})

const hasResults = computed(() => {
  return subdomainResults.value.length > 0 || summaryData.value !== null
})

// Helper functions
const getSourceColor = (source) => {
  const colors = {
    'crt.sh': 'primary',
    HackerTarget: 'success',
    SecurityTrails: 'warning',
  }
  return colors[source] || 'grey'
}

const getSourceIcon = (source) => {
  const icons = {
    'crt.sh': 'mdi-certificate',
    HackerTarget: 'mdi-target',
    SecurityTrails: 'mdi-security',
  }
  return icons[source] || 'mdi-source-merge'
}

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}

const copyAllSubdomains = () => {
  const subdomains = sortedSubdomains.value.map((s) => s.subdomain).join('\n')
  copyToClipboard(subdomains)
}

const copyResolvedOnly = () => {
  const resolved = sortedSubdomains.value
    .filter((s) => s.resolved && s.ip)
    .map((s) => s.subdomain)
    .join('\n')
  copyToClipboard(resolved)
}

const copyAsHostsFile = () => {
  const hosts = sortedSubdomains.value
    .filter((s) => s.resolved && s.ip)
    .map((s) => `${s.ip}\t${s.subdomain}`)
    .join('\n')
  copyToClipboard(hosts)
}
</script>

<style scoped>
.subdomain-results-grid {
  margin-top: 1.5rem;
}

.subdomain-card {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.subdomain-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgb(0 0 0 / 12%);
}

.summary-card {
  background: linear-gradient(
    135deg,
    rgb(var(--v-theme-surface)) 0%,
    rgb(var(--v-theme-surface-variant), 0.05) 100%
  );
}

.bg-gradient-primary {
  background: linear-gradient(
    45deg,
    rgb(var(--v-theme-primary), 0.12),
    rgb(var(--v-theme-primary), 0.05)
  );
}

.bg-primary-lighten-5 {
  background: linear-gradient(
    45deg,
    rgb(var(--v-theme-primary), 0.08),
    rgb(var(--v-theme-primary), 0.03)
  );
}

pre {
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

code {
  font-family: 'Roboto Mono', monospace;
  font-size: 0.875rem;
}

/* Custom scrollbar for better UX */
.subdomain-results-grid {
  max-height: 600px;
  overflow-y: auto;
}

.subdomain-results-grid::-webkit-scrollbar {
  width: 8px;
}

.subdomain-results-grid::-webkit-scrollbar-track {
  background: rgb(var(--v-theme-surface-variant), 0.1);
  border-radius: 4px;
}

.subdomain-results-grid::-webkit-scrollbar-thumb {
  background: rgb(var(--v-theme-primary), 0.3);
  border-radius: 4px;
}

.subdomain-results-grid::-webkit-scrollbar-thumb:hover {
  background: rgb(var(--v-theme-primary), 0.5);
}

/* Ensure text doesn't overflow */
.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
