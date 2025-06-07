<template>
  <v-dialog
    v-model="show"
    max-width="800px"
    scrollable
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2">
          <v-icon icon="mdi-file-image" />
          <span>File Metadata</span>
        </div>
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          @click="show = false"
        />
      </v-card-title>

      <v-card-text class="pa-0">
        <!-- Loading State -->
        <div v-if="loading" class="d-flex justify-center pa-8">
          <v-progress-circular
            indeterminate
            :size="50"
            :width="6"
            color="primary"
          />
        </div>

        <!-- Error State -->
        <v-alert
          v-else-if="error"
          type="error"
          variant="outlined"
          class="ma-4"
        >
          {{ error }}
        </v-alert>

        <!-- Metadata Content -->
        <div v-else-if="metadata" class="pa-4">
          <!-- File Information -->
          <v-card v-if="metadata.file_info" class="mb-4" variant="outlined">
            <v-card-title class="d-flex align-center ga-2">
              <v-icon icon="mdi-file" />
              <span>Information</span>
            </v-card-title>
            <v-card-text>
              <v-row dense>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">Filename</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.file_info.filename }}</div>
                </v-col>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">File Type</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.file_info.file_type }}</div>
                </v-col>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">MIME Type</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.file_info.mime_type }}</div>
                </v-col>
                <v-col cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">File Size</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.file_info.file_size }}</div>
                </v-col>
                <v-col v-if="metadata.file_info.dimensions" cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">Dimensions</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.file_info.dimensions }}</div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- GPS Information (highlighted if available) -->
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
              <v-row dense>
                <v-col v-if="metadata.gps_info.coordinates" cols="12">
                  <div class="text-caption text-medium-emphasis">Coordinates</div>
                  <div class="d-flex align-center ga-2">
                    <div class="text-body-2 font-weight-medium">{{ metadata.gps_info.coordinates }}</div>
                    <v-btn
                      icon="mdi-content-copy"
                      size="x-small"
                      variant="text"
                      @click="copyToClipboard(metadata.gps_info.coordinates)"
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
                <v-col v-if="metadata.gps_info.altitude" cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">Altitude</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.gps_info.altitude }}</div>
                </v-col>
                <v-col v-if="metadata.gps_info.timestamp" cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">GPS Timestamp</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.gps_info.timestamp }}</div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Camera Information -->
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
              <v-row dense>
                <v-col v-if="metadata.camera_info.make" cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">Make</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.camera_info.make }}</div>
                </v-col>
                <v-col v-if="metadata.camera_info.model" cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">Model</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.camera_info.model }}</div>
                </v-col>
                <v-col v-if="metadata.camera_info.lens" cols="12">
                  <div class="text-caption text-medium-emphasis">Lens</div>
                  <div class="text-body-2 font-weight-medium">{{ metadata.camera_info.lens }}</div>
                </v-col>
              </v-row>

              <!-- Camera Settings -->
              <div v-if="metadata.camera_info.settings" class="mt-3">
                <div class="text-caption text-medium-emphasis mb-2">Camera Settings</div>
                <v-row dense>
                  <v-col v-for="(value, key) in metadata.camera_info.settings" :key="key" cols="6" sm="3">
                    <v-chip size="small" variant="outlined">
                      {{ formatSettingName(key) }}: {{ value }}
                    </v-chip>
                  </v-col>
                </v-row>
              </div>
            </v-card-text>
          </v-card>

          <!-- Timestamp Information -->
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
              <v-row dense>
                <v-col v-for="(value, key) in metadata.timestamp_info" :key="key" cols="12" sm="6">
                  <div class="text-caption text-medium-emphasis">{{ formatTimestampName(key) }}</div>
                  <div class="text-body-2 font-weight-medium">{{ value }}</div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Detailed Metadata (Expandable) -->
          <v-expansion-panels v-if="metadata.categories" variant="accordion">
            <v-expansion-panel
              v-for="(categoryData, categoryName) in metadata.categories"
              :key="categoryName"
              v-show="Object.keys(categoryData).length > 0"
            >
              <v-expansion-panel-title>
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
                      <div class="flex-grow-1">
                        <div class="text-caption text-medium-emphasis">
                          {{ formatFieldName(key) }}
                        </div>
                        <div class="text-body-2 font-weight-medium">
                          {{ formatFieldValue(key, value) }}
                        </div>
                      </div>
                      <v-btn
                        icon="mdi-content-copy"
                        size="x-small"
                        variant="text"
                        @click="copyToClipboard(value)"
                      >
                        <v-tooltip activator="parent">Copy value</v-tooltip>
                      </v-btn>
                    </div>
                  </div>
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <!-- Summary -->
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
        <v-btn color="primary" variant="text" @click="show = false">
          Close
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  evidenceItem: {
    type: Object,
    default: null
  },
  metadata: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

const show = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// Get category icon
const getCategoryIcon = (categoryName) => {
  const icons = {
    camera: 'mdi-camera',
    gps: 'mdi-map-marker',
    timestamps: 'mdi-clock-outline',
    technical: 'mdi-cog',
    other: 'mdi-information-outline'
  }
  return icons[categoryName] || 'mdi-information-outline'
}

// Format field names for better readability
const formatFieldName = (fieldName) => {
  // Remove prefixes like "EXIF:", "File:", etc.
  const cleanName = fieldName.replace(/^(EXIF|File|Composite|GPS):/i, '')

  // Add spaces before capital letters and format
  return cleanName
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/([A-Z])([A-Z][a-z])/g, '$1 $2')
    .trim()
}

// Format field values for better display
const formatFieldValue = (fieldName, value) => {
  if (value === null || value === undefined) return 'N/A'

  // Handle boolean values
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }

  // Truncate very long strings
  const stringValue = String(value)
  if (stringValue.length > 200) {
    return stringValue.substring(0, 200) + '...'
  }

  return stringValue
}

// Format setting names
const formatSettingName = (settingKey) => {
  return settingKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

// Format timestamp names
const formatTimestampName = (timestampKey) => {
  const names = {
    taken: 'Date Taken',
    created: 'Date Created',
    modified: 'Date Modified'
  }
  return names[timestampKey] || timestampKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

// Copy to clipboard
const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(String(text))
    // Could add toast notification here
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}

// Open GPS coordinates in Google Maps
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
  gap: 8px;
}

.metadata-item {
  background-color: rgba(var(--v-theme-surface-variant), 0.1);
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  transition: background-color 0.2s ease;
}

.metadata-item:hover {
  background-color: rgba(var(--v-theme-surface-variant), 0.2);
}

@media (max-width: 600px) {
  .metadata-grid {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 601px) {
  .metadata-grid {
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  }
}

:deep(.v-expansion-panel-title) {
  padding: 12px 16px;
}

:deep(.v-expansion-panel-text) {
  padding: 0 16px 16px;
}
</style>
