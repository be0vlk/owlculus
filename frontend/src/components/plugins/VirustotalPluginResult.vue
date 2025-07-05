<template>
  <div class="d-flex flex-column ga-4">
    <!-- Status Messages -->
    <PluginStatusAlert
      v-for="(item, index) in statusMessages"
      :key="`status-${index}`"
      type="status"
      :message="item.data.message"
    />

    <!-- VirusTotal Results -->
    <div v-if="virusTotalResults.length" class="vt-results-grid">
      <v-row>
        <v-col v-for="(result, index) in virusTotalResults" :key="`vt-${index}`" cols="12">
          <v-card elevation="2" rounded="lg" class="result-card">
            <!-- Result Header -->
            <v-card-title class="d-flex align-center bg-primary-lighten-5 pa-4">
              <v-icon :icon="getTargetIcon(result.target_type)" size="large" class="mr-3" />
              <div class="flex-grow-1">
                <div class="text-h6 d-flex align-center ga-2">
                  <span class="text-truncate" style="max-width: 400px">{{ result.target }}</span>
                  <v-btn
                    icon="mdi-content-copy"
                    size="x-small"
                    variant="text"
                    @click="copyToClipboard(result.target)"
                  >
                    <v-tooltip activator="parent" location="top">Copy target</v-tooltip>
                  </v-btn>
                </div>
                <div class="text-caption text-medium-emphasis">
                  {{ formatTargetType(result.target_type) }}
                </div>
              </div>

              <!-- Verdict Chip -->
              <v-chip
                :color="getVerdictColor(result.verdict)"
                variant="elevated"
                size="large"
                class="font-weight-bold"
              >
                <v-icon :icon="getVerdictIcon(result.verdict)" size="small" class="mr-1" />
                {{ result.verdict }}
              </v-chip>
            </v-card-title>

            <v-card-text class="pa-0">
              <div class="pa-4">
                <!-- Detection Summary -->
                <div class="mb-4">
                  <div class="d-flex align-center justify-space-between mb-2">
                    <span class="text-subtitle1 font-weight-medium">Detection Ratio</span>
                    <span
                      :class="getDetectionColor(result.detection_ratio)"
                      class="text-h5 font-weight-bold"
                    >
                      {{ result.detection_ratio }}
                    </span>
                  </div>
                  <v-progress-linear
                    :model-value="getDetectionPercentage(result.detection_ratio)"
                    :color="getDetectionProgressColor(result.detection_ratio)"
                    height="10"
                    rounded
                    class="detection-progress"
                  />
                  <div class="text-caption text-medium-emphasis mt-2">
                    <v-icon icon="mdi-clock-outline" size="x-small" />
                    Last analysis: {{ result.last_analysis_date }}
                  </div>
                </div>

                <!-- Target-specific Information -->
                <div v-if="result.file_info" class="mb-4">
                  <div class="text-subtitle2 font-weight-medium mb-2">File Information</div>
                  <v-list density="compact" class="pa-0">
                    <v-list-item v-if="result.file_info.sha256" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">SHA256:</span>
                      </template>
                      <v-list-item-title class="text-body-2 font-mono d-flex align-center ga-2">
                        <span class="text-truncate">{{ result.file_info.sha256 }}</span>
                        <v-btn
                          icon="mdi-content-copy"
                          size="x-small"
                          variant="text"
                          @click="copyToClipboard(result.file_info.sha256)"
                        >
                          <v-tooltip activator="parent" location="top">Copy SHA256</v-tooltip>
                        </v-btn>
                      </v-list-item-title>
                    </v-list-item>
                    <v-list-item v-if="result.file_info.size" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">Size:</span>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ formatFileSize(result.file_info.size) }}
                      </v-list-item-title>
                    </v-list-item>
                    <v-list-item v-if="result.file_info.type" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">Type:</span>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ result.file_info.type }}
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>

                  <!-- File Names -->
                  <div v-if="result.file_info.names && result.file_info.names.length" class="mt-3">
                    <div class="text-body-2 font-weight-medium mb-1">Known Filenames:</div>
                    <div class="d-flex flex-wrap ga-1">
                      <v-chip
                        v-for="(name, nIndex) in result.file_info.names.slice(0, 5)"
                        :key="`name-${nIndex}`"
                        size="small"
                        variant="outlined"
                        color="info"
                      >
                        {{ name }}
                      </v-chip>
                      <v-chip
                        v-if="result.file_info.names.length > 5"
                        size="small"
                        variant="text"
                        color="grey"
                      >
                        +{{ result.file_info.names.length - 5 }} more
                      </v-chip>
                    </div>
                  </div>
                </div>

                <!-- URL Information -->
                <div v-if="result.url_info" class="mb-4">
                  <div class="text-subtitle2 font-weight-medium mb-2">URL Information</div>
                  <v-list density="compact" class="pa-0">
                    <v-list-item v-if="result.url_info.final_url" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">Final URL:</span>
                      </template>
                      <v-list-item-title class="text-body-2 text-truncate">
                        {{ result.url_info.final_url }}
                      </v-list-item-title>
                    </v-list-item>
                    <v-list-item v-if="result.url_info.title" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">Title:</span>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ result.url_info.title }}
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>
                </div>

                <!-- Domain Information -->
                <div v-if="result.domain_info" class="mb-4">
                  <div class="text-subtitle2 font-weight-medium mb-2">Domain Information</div>
                  <v-list density="compact" class="pa-0">
                    <v-list-item v-if="result.domain_info.registrar" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">Registrar:</span>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ result.domain_info.registrar }}
                      </v-list-item-title>
                    </v-list-item>
                    <v-list-item v-if="result.domain_info.creation_date" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">Created:</span>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ result.domain_info.creation_date }}
                      </v-list-item-title>
                    </v-list-item>
                    <v-list-item v-if="result.domain_info.reputation !== null" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">Reputation:</span>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ result.domain_info.reputation }}
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>
                </div>

                <!-- IP Information -->
                <div v-if="result.ip_info" class="mb-4">
                  <div class="text-subtitle2 font-weight-medium mb-2">IP Information</div>
                  <v-list density="compact" class="pa-0">
                    <v-list-item v-if="result.ip_info.asn" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">ASN:</span>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ result.ip_info.asn }}
                      </v-list-item-title>
                    </v-list-item>
                    <v-list-item v-if="result.ip_info.as_owner" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">AS Owner:</span>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ result.ip_info.as_owner }}
                      </v-list-item-title>
                    </v-list-item>
                    <v-list-item v-if="result.ip_info.country" class="px-0">
                      <template #prepend>
                        <span class="text-body-2 font-weight-medium mr-2">Country:</span>
                      </template>
                      <v-list-item-title class="text-body-2">
                        {{ result.ip_info.country }}
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>
                </div>

                <!-- Categories -->
                <div v-if="result.categories && Object.keys(result.categories).length" class="mb-4">
                  <div class="text-subtitle2 font-weight-medium mb-2">Categories</div>
                  <div class="d-flex flex-wrap ga-1">
                    <v-chip
                      v-for="(category, vendor) in result.categories"
                      :key="`cat-${vendor}`"
                      size="small"
                      variant="tonal"
                      color="primary"
                    >
                      <span class="text-caption font-weight-medium">{{ vendor }}:</span>
                      <span class="ml-1">{{ category }}</span>
                    </v-chip>
                  </div>
                </div>

                <!-- Tags -->
                <div v-if="result.tags && result.tags.length" class="mb-4">
                  <div class="text-subtitle2 font-weight-medium mb-2">Tags</div>
                  <div class="d-flex flex-wrap ga-1">
                    <v-chip
                      v-for="(tag, tIndex) in result.tags"
                      :key="`tag-${tIndex}`"
                      size="small"
                      variant="outlined"
                      color="secondary"
                    >
                      {{ tag }}
                    </v-chip>
                  </div>
                </div>

                <!-- Vendor Detections -->
                <div v-if="result.detections && result.detections.length">
                  <v-divider class="mb-3" />
                  <v-expansion-panels variant="accordion">
                    <v-expansion-panel elevation="0">
                      <v-expansion-panel-title class="text-subtitle2 font-weight-medium pa-0 pb-2">
                        <div class="d-flex align-center">
                          <v-icon icon="mdi-shield-search" size="small" class="mr-2" />
                          Vendor Detections ({{ result.detections.length }})
                        </div>
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <v-list density="compact" class="pa-0">
                          <v-list-item
                            v-for="(detection, dIndex) in result.detections"
                            :key="`detection-${dIndex}`"
                            class="px-0"
                          >
                            <template #prepend>
                              <v-chip
                                size="x-small"
                                :color="getDetectionCategoryColor(detection.category)"
                                variant="tonal"
                                class="mr-3"
                              >
                                {{ detection.category }}
                              </v-chip>
                            </template>
                            <v-list-item-title class="text-body-2">
                              <span class="font-weight-medium">{{ detection.vendor }}:</span>
                              <span class="ml-2 text-error">{{ detection.result }}</span>
                            </v-list-item-title>
                          </v-list-item>
                        </v-list>
                      </v-expansion-panel-text>
                    </v-expansion-panel>
                  </v-expansion-panels>
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
      plugin-name="VirusTotal"
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

// Extract VirusTotal data results
const virusTotalResults = computed(() => {
  return parsedResults.value.filter((item) => item.type === 'data').map((item) => item.data)
})

// Helper functions
const getTargetIcon = (targetType) => {
  switch (targetType) {
    case 'file':
      return 'mdi-file-document-outline'
    case 'url':
      return 'mdi-link'
    case 'domain':
      return 'mdi-web'
    case 'ip_address':
      return 'mdi-ip-network'
    default:
      return 'mdi-magnify'
  }
}

const formatTargetType = (targetType) => {
  switch (targetType) {
    case 'file':
      return 'File Hash'
    case 'url':
      return 'URL'
    case 'domain':
      return 'Domain'
    case 'ip_address':
      return 'IP Address'
    default:
      return targetType
  }
}

const getVerdictColor = (verdict) => {
  switch (verdict) {
    case 'Clean':
      return 'success'
    case 'Likely Safe':
      return 'success'
    case 'Suspicious':
      return 'warning'
    case 'Likely Malicious':
      return 'error'
    case 'Malicious':
      return 'error'
    default:
      return 'grey'
  }
}

const getVerdictIcon = (verdict) => {
  switch (verdict) {
    case 'Clean':
      return 'mdi-shield-check'
    case 'Likely Safe':
      return 'mdi-shield-check'
    case 'Suspicious':
      return 'mdi-shield-alert'
    case 'Likely Malicious':
      return 'mdi-shield-remove'
    case 'Malicious':
      return 'mdi-shield-off'
    default:
      return 'mdi-shield-outline'
  }
}

const getDetectionPercentage = (ratio) => {
  if (!ratio) return 0
  const [detected, total] = ratio.split('/').map((n) => parseInt(n))
  if (total === 0) return 0
  return (detected / total) * 100
}

const getDetectionColor = (ratio) => {
  const percentage = getDetectionPercentage(ratio)
  if (percentage === 0) return 'text-success'
  if (percentage < 10) return 'text-success'
  if (percentage < 30) return 'text-warning'
  return 'text-error'
}

const getDetectionProgressColor = (ratio) => {
  const percentage = getDetectionPercentage(ratio)
  if (percentage === 0) return 'success'
  if (percentage < 10) return 'success'
  if (percentage < 30) return 'warning'
  return 'error'
}

const getDetectionCategoryColor = (category) => {
  const categoryColors = {
    malware: 'error',
    phishing: 'error',
    malicious: 'error',
    suspicious: 'warning',
    undetected: 'success',
    harmless: 'success',
    'type-unsupported': 'grey',
  }
  return categoryColors[category?.toLowerCase()] || 'info'
}

const formatFileSize = (bytes) => {
  if (!bytes) return 'Unknown'
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  if (bytes === 0) return '0 Bytes'
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
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
.result-card {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.result-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgb(0 0 0 / 12%);
}

.vt-results-grid {
  margin-top: 1.5rem;
}

.bg-primary-lighten-5 {
  background: linear-gradient(
    45deg,
    rgb(var(--v-theme-primary), 0.08),
    rgb(var(--v-theme-primary), 0.03)
  );
}

.font-mono {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.85em;
}

.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Enhanced visual hierarchy */
.v-chip[color='success'] {
  background: rgb(var(--v-theme-success), 0.12);
  border: 1px solid rgb(var(--v-theme-success), 0.3);
}

.v-chip[color='warning'] {
  background: rgb(var(--v-theme-warning), 0.12);
  border: 1px solid rgb(var(--v-theme-warning), 0.3);
}

.v-chip[color='error'] {
  background: rgb(var(--v-theme-error), 0.12);
  border: 1px solid rgb(var(--v-theme-error), 0.3);
}

/* Progress bar styling */
.v-progress-linear {
  background: rgb(var(--v-theme-surface-variant), 0.3);
}

.detection-progress {
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.1);
}

.detection-progress .v-progress-linear__determinate {
  transition: width 0.6s ease;
}
</style>
