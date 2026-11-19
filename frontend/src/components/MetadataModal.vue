<template>
  <v-dialog v-model="show" aria-label="File Metadata" max-width="800px" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2">
          <v-icon icon="mdi-file-image" />
          <span>File Metadata</span>
        </div>
        <v-btn
          icon="mdi-close"
          aria-label="Close metadata"
          size="small"
          variant="text"
          @click="show = false"
        />
      </v-card-title>

      <v-card-text class="pa-0">
        <div v-if="loading" class="d-flex justify-center pa-8">
          <v-progress-circular :size="50" :width="6" color="primary" indeterminate />
        </div>

        <v-alert v-else-if="error" class="ma-4" type="error" variant="outlined">
          {{ error }}
        </v-alert>

        <div v-else-if="metadata" class="pa-4">
          <v-card v-if="metadata.file_info" class="mb-4" variant="outlined">
            <v-card-title class="d-flex align-center ga-2">
              <v-icon icon="mdi-file" />
              <span>Information</span>
            </v-card-title>
            <v-card-text>
              <v-row density="compact">
                <template v-for="[label, key] in FILE_FIELDS" :key="key">
                  <v-col v-if="metadata.file_info[key] != null" cols="12" sm="6">
                    <div class="text-body-small text-medium-emphasis">{{ label }}</div>
                    <div class="text-body-medium font-weight-medium">
                      {{ metadata.file_info[key] }}
                    </div>
                  </v-col>
                </template>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card
            v-if="metadata.gps_info && Object.keys(metadata.gps_info).length > 0"
            class="mb-4"
            color="blue-lighten-5"
            variant="outlined"
          >
            <v-card-title class="d-flex align-center ga-2">
              <v-icon icon="mdi-map-marker" color="blue" />
              <span>GPS Location</span>
            </v-card-title>
            <v-card-text>
              <v-row density="compact">
                <v-col v-if="metadata.gps_info.coordinates" cols="12">
                  <div class="text-body-small text-medium-emphasis">Coordinates</div>
                  <div class="d-flex align-center ga-2">
                    <div class="text-body-medium font-weight-medium">
                      {{ metadata.gps_info.coordinates }}
                    </div>
                    <v-btn
                      icon="mdi-content-copy"
                      size="x-small"
                      variant="text"
                      @click="copyToClipboard(String(metadata.gps_info.coordinates))"
                    >
                      <v-tooltip activator="parent">Copy coordinates</v-tooltip>
                    </v-btn>
                    <v-btn
                      icon="mdi-open-in-new"
                      size="x-small"
                      variant="text"
                      @click="openInMaps(metadata.gps_info.coordinates)"
                    >
                      <v-tooltip activator="parent">Open in Google Maps</v-tooltip>
                    </v-btn>
                  </div>
                </v-col>
                <template v-for="[label, key] in GPS_FIELDS" :key="key">
                  <v-col v-if="metadata.gps_info[key]" cols="12" sm="6">
                    <div class="text-body-small text-medium-emphasis">{{ label }}</div>
                    <div class="text-body-medium font-weight-medium">
                      {{ metadata.gps_info[key] }}
                    </div>
                  </v-col>
                </template>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card
            v-if="metadata.camera_info && Object.keys(metadata.camera_info).length > 0"
            class="mb-4"
            variant="outlined"
          >
            <v-card-title class="d-flex align-center ga-2">
              <v-icon icon="mdi-camera" />
              <span>Camera Information</span>
            </v-card-title>
            <v-card-text>
              <v-row density="compact">
                <template v-for="[label, key] in CAMERA_FIELDS" :key="key">
                  <v-col v-if="metadata.camera_info[key]" cols="12" sm="6">
                    <div class="text-body-small text-medium-emphasis">{{ label }}</div>
                    <div class="text-body-medium font-weight-medium">
                      {{ metadata.camera_info[key] }}
                    </div>
                  </v-col>
                </template>
              </v-row>

              <div v-if="metadata.camera_info.settings" class="mt-3">
                <div class="text-body-small text-medium-emphasis mb-2">Camera Settings</div>
                <v-row density="compact">
                  <v-col
                    v-for="(value, key) in metadata.camera_info.settings"
                    :key="key"
                    cols="6"
                    sm="3"
                  >
                    <v-chip size="small" variant="outlined">
                      {{ formatParameterName(key) }}: {{ value }}
                    </v-chip>
                  </v-col>
                </v-row>
              </div>
            </v-card-text>
          </v-card>

          <v-card
            v-if="metadata.timestamp_info && Object.keys(metadata.timestamp_info).length > 0"
            class="mb-4"
            variant="outlined"
          >
            <v-card-title class="d-flex align-center ga-2">
              <v-icon icon="mdi-clock-outline" />
              <span>Timestamps</span>
            </v-card-title>
            <v-card-text>
              <v-row density="compact">
                <v-col v-for="(value, key) in metadata.timestamp_info" :key="key" cols="12" sm="6">
                  <div class="text-body-small text-medium-emphasis">
                    {{ TIMESTAMP_NAMES[key] || formatParameterName(key) }}
                  </div>
                  <div class="text-body-medium font-weight-medium">{{ value }}</div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-expansion-panels v-if="metadata.categories" variant="accordion">
            <v-expansion-panel
              v-for="(categoryData, categoryName) in metadata.categories"
              :key="categoryName"
              v-show="Object.keys(categoryData).length > 0"
            >
              <v-expansion-panel-title class="metadata-panel-title">
                <div class="d-flex align-center ga-2">
                  <v-icon :icon="getCategoryIcon(categoryName)" />
                  <span class="text-capitalize">{{ categoryName }} Metadata</span>
                  <v-chip size="small" variant="outlined">
                    {{ Object.keys(categoryData).length }} fields
                  </v-chip>
                </div>
              </v-expansion-panel-title>

              <v-expansion-panel-text>
                <div class="metadata-grid">
                  <div
                    v-for="(value, key) in categoryData"
                    :key="key"
                    class="metadata-item pa-3 mb-2"
                  >
                    <div class="d-flex justify-space-between align-start">
                      <div class="flex-grow-1" style="min-width: 0; overflow: hidden">
                        <div class="text-body-small text-medium-emphasis text-truncate">
                          {{ formatFieldName(key) }}
                        </div>
                        <div class="text-body-medium font-weight-medium text-break">
                          {{ formatFieldValue(key, value) }}
                        </div>
                      </div>
                      <v-btn
                        icon="mdi-content-copy"
                        size="x-small"
                        variant="text"
                        @click="copyToClipboard(String(value))"
                      >
                        <v-tooltip activator="parent">Copy value</v-tooltip>
                      </v-btn>
                    </div>
                  </div>
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <v-card v-if="metadata.total_fields" class="mt-4" variant="outlined">
            <v-card-text class="text-center">
              <v-icon icon="mdi-information" class="mr-2" />
              <strong>{{ metadata.total_fields }}</strong> total metadata fields extracted
            </v-card-text>
          </v-card>
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn color="primary" variant="text" @click="show = false"> Close </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { copyToClipboard } from '@/utils/clipboard'
import { formatParameterName } from '@/utils/huntDisplayUtils'

defineProps({
  metadata: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
})

const show = defineModel({ type: Boolean, default: false })

const FILE_FIELDS = [
  ['Filename', 'filename'],
  ['File Type', 'file_type'],
  ['MIME Type', 'mime_type'],
  ['File Size', 'file_size'],
  ['Dimensions', 'dimensions'],
]
const GPS_FIELDS = [
  ['Altitude', 'altitude'],
  ['GPS Timestamp', 'timestamp'],
]
const CAMERA_FIELDS = [
  ['Make', 'make'],
  ['Model', 'model'],
  ['Lens', 'lens'],
]
const TIMESTAMP_NAMES = { taken: 'Date Taken', created: 'Date Created', modified: 'Date Modified' }

const getCategoryIcon = (categoryName) => {
  const icons = {
    camera: 'mdi-camera',
    gps: 'mdi-map-marker',
    timestamps: 'mdi-clock-outline',
    technical: 'mdi-cog',
    other: 'mdi-information-outline',
  }
  return icons[categoryName] || 'mdi-information-outline'
}

const formatFieldName = (fieldName) => {
  const cleanName = fieldName.replace(/^(EXIF|File|Composite|GPS):/i, '')

  return cleanName
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/([A-Z])([A-Z][a-z])/g, '$1 $2')
    .trim()
}

const formatFieldValue = (fieldName, value) => {
  if (value === null || value === undefined) return 'N/A'

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }

  const stringValue = String(value)
  if (stringValue.length > 200) {
    return stringValue.substring(0, 200) + '...'
  }

  return stringValue
}

const openInMaps = (coordinates) => {
  if (coordinates) {
    const mapsUrl = `https://www.google.com/maps?q=${encodeURIComponent(coordinates)}`
    window.open(mapsUrl, '_blank')
  }
}
</script>

<style scoped>
.metadata-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr));
  gap: 8px;
}

.metadata-item {
  background-color: rgb(var(--v-theme-surface-variant), 0.1);
  border-radius: 8px;
  border: 1px solid rgb(var(--v-theme-outline), 0.2);
  transition: background-color 0.2s ease;
  overflow: hidden;
  word-wrap: break-word;
}

.metadata-item:hover {
  background-color: rgb(var(--v-theme-surface-variant), 0.2);
}

.metadata-panel-title {
  padding: 12px 16px;
}
</style>
