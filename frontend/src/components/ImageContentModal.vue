<template>
  <v-dialog
    v-model="show"
    max-width="1200px"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2">
          <v-icon icon="mdi-file-image-box" />
          <span>Image Preview</span>
        </div>
        <v-btn icon="mdi-close" size="small" variant="text" @click="show = false" />
      </v-card-title>

      <v-card-text class="pa-0">
        <!-- Loading State -->
        <div v-if="loading" class="d-flex justify-center pa-8">
          <v-progress-circular :size="50" :width="6" color="primary" indeterminate />
        </div>

        <!-- Error State -->
        <v-alert v-else-if="error" class="ma-4" type="error" variant="outlined">
          {{ error }}
        </v-alert>

        <!-- Image Display -->
        <div v-else-if="imageUrl" class="d-flex flex-column">
          <!-- Image Information Header -->
          <v-card v-if="fileInfo" class="ma-4 mb-2" variant="outlined">
            <v-card-text class="py-3">
              <v-row dense align="center">
                <v-col cols="12" sm="6" md="3">
                  <div class="text-caption text-medium-emphasis">File</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ fileInfo.filename || evidenceItem?.title }}
                  </div>
                </v-col>
                <v-col cols="12" sm="6" md="2">
                  <div class="text-caption text-medium-emphasis">Size</div>
                  <div class="text-body-2 font-weight-medium">
                    {{ formatFileSize(fileInfo.file_size) }}
                  </div>
                </v-col>
                <v-col cols="12" sm="6" md="2">
                  <div class="text-caption text-medium-emphasis">Dimensions</div>
                  <div class="text-body-2 font-weight-medium">{{ imageDimensions }}</div>
                </v-col>
                <v-col cols="12" sm="6" md="2">
                  <div class="text-caption text-medium-emphasis">Format</div>
                  <div class="text-body-2 font-weight-medium">{{ imageFormat }}</div>
                </v-col>
                <v-col cols="12" md="3" class="d-flex justify-end ga-2">
                  <v-btn
                    size="small"
                    variant="outlined"
                    prepend-icon="mdi-download"
                    @click="downloadImage"
                  >
                    Download
                  </v-btn>
                  <v-btn
                    size="small"
                    variant="outlined"
                    prepend-icon="mdi-fullscreen"
                    @click="toggleFullscreen"
                  >
                    Fullscreen
                  </v-btn>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Zoom Controls -->
          <div class="mx-4 mb-2 d-flex align-center ga-2">
            <v-btn
              size="small"
              icon="mdi-magnify-minus"
              variant="outlined"
              @click="zoomOut"
              :disabled="zoomLevel <= 0.25"
            />
            <v-chip size="small" variant="outlined"> {{ Math.round(zoomLevel * 100) }}% </v-chip>
            <v-btn
              size="small"
              icon="mdi-magnify-plus"
              variant="outlined"
              @click="zoomIn"
              :disabled="zoomLevel >= 3"
            />
            <v-btn size="small" variant="outlined" @click="resetZoom"> Reset </v-btn>
            <v-spacer />
            <v-btn-toggle v-model="fitMode" density="compact" mandatory variant="outlined">
              <v-btn value="contain" size="small">
                <v-icon>mdi-fit-to-screen-outline</v-icon>
                <v-tooltip activator="parent" location="top">Fit to screen</v-tooltip>
              </v-btn>
              <v-btn value="actual" size="small">
                <v-icon>mdi-image-size-select-actual</v-icon>
                <v-tooltip activator="parent" location="top">Actual size</v-tooltip>
              </v-btn>
            </v-btn-toggle>
          </div>

          <!-- Image Container -->
          <div
            ref="imageContainer"
            class="image-container flex-grow-1"
            @wheel.prevent="handleWheel"
          >
            <div :style="imageWrapperStyle" class="image-wrapper">
              <img
                ref="imageElement"
                :src="imageUrl"
                :alt="evidenceItem?.title || 'Evidence image'"
                class="evidence-image"
                :style="imageStyle"
                @load="handleImageLoad"
                @error="handleImageError"
              />
            </div>
          </div>
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
import { computed, ref, watch } from 'vue'
import { evidenceService } from '../services/evidence'
import api from '../services/api'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  evidenceItem: {
    type: Object,
    default: null,
  },
  fileInfo: {
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

const emit = defineEmits(['update:modelValue'])

// Reactive data
const imageUrl = ref('')
const zoomLevel = ref(1)
const fitMode = ref('contain')
const imageDimensions = ref('')
const imageFormat = ref('')
const imageElement = ref(null)
const imageContainer = ref(null)
const naturalWidth = ref(0)
const naturalHeight = ref(0)

const show = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

// Computed styles
const imageWrapperStyle = computed(() => {
  if (fitMode.value === 'contain') {
    return {
      width: '100%',
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }
  }
  return {
    width: '100%',
    height: '100%',
    overflow: 'auto',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  }
})

const imageStyle = computed(() => {
  if (fitMode.value === 'contain') {
    return {
      maxWidth: '100%',
      maxHeight: '100%',
      width: 'auto',
      height: 'auto',
      transform: `scale(${zoomLevel.value})`,
      transition: 'transform 0.2s ease',
    }
  }
  return {
    transform: `scale(${zoomLevel.value})`,
    transition: 'transform 0.2s ease',
    transformOrigin: 'center',
  }
})

// Format file size for display
const formatFileSize = (bytes) => {
  if (!bytes) return 'Unknown'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }

  return `${size.toFixed(unitIndex > 0 ? 1 : 0)} ${units[unitIndex]}`
}

// Handle image load
const handleImageLoad = (event) => {
  const img = event.target
  naturalWidth.value = img.naturalWidth
  naturalHeight.value = img.naturalHeight
  imageDimensions.value = `${img.naturalWidth} × ${img.naturalHeight}`

  // Detect format from file extension
  const filename = props.evidenceItem?.title || ''
  const extension = filename.split('.').pop()?.toUpperCase() || 'Unknown'
  imageFormat.value = extension
}

// Handle image error
const handleImageError = () => {
  imageUrl.value = ''
}

// Zoom controls
const zoomIn = () => {
  zoomLevel.value = Math.min(zoomLevel.value * 1.2, 3)
}

const zoomOut = () => {
  zoomLevel.value = Math.max(zoomLevel.value / 1.2, 0.25)
}

const resetZoom = () => {
  zoomLevel.value = 1
}

const handleWheel = (event) => {
  if (event.ctrlKey || event.metaKey) {
    event.preventDefault()
    if (event.deltaY < 0) {
      zoomIn()
    } else {
      zoomOut()
    }
  }
}

// Download image
const downloadImage = async () => {
  if (!props.evidenceItem) return

  try {
    const blob = await evidenceService.downloadEvidence(props.evidenceItem.id)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = props.evidenceItem.title
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  } catch (err) {
    console.error('Failed to download image:', err)
  }
}

// Toggle fullscreen
const toggleFullscreen = () => {
  const elem = imageContainer.value
  if (!elem) return

  if (!document.fullscreenElement) {
    elem.requestFullscreen().catch((err) => {
      console.error('Failed to enter fullscreen:', err)
    })
  } else {
    document.exitFullscreen()
  }
}

// Fetch image when evidence item changes
const fetchImage = async (evidenceItem) => {
  if (!evidenceItem || !evidenceItem.id) {
    imageUrl.value = ''
    return
  }

  try {
    // Fetch the image with authentication
    const response = await api.get(`/api/evidence/${evidenceItem.id}/image`, {
      responseType: 'blob',
    })

    // Create a blob URL from the response
    const blob = new Blob([response.data], { type: response.headers['content-type'] })
    imageUrl.value = URL.createObjectURL(blob)
  } catch (error) {
    console.error('Failed to load image:', error)
    imageUrl.value = ''
  }
}

// Set image URL when evidence item changes
watch(
  () => props.evidenceItem,
  (newItem) => {
    fetchImage(newItem)
  },
  { immediate: true },
)

// Reset state when modal closes
watch(show, (newValue) => {
  if (!newValue) {
    // Clean up blob URL to prevent memory leak
    if (imageUrl.value && imageUrl.value.startsWith('blob:')) {
      URL.revokeObjectURL(imageUrl.value)
    }
    imageUrl.value = ''
    zoomLevel.value = 1
    fitMode.value = 'contain'
    imageDimensions.value = ''
    imageFormat.value = ''
  }
})
</script>

<style scoped>
.image-container {
  max-height: 70vh;
  min-height: 400px;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  margin: 0 16px 16px;
  border-radius: 8px;
  background-color: rgba(var(--v-theme-surface-variant), 0.05);
  overflow: hidden;
  position: relative;
}

.image-wrapper {
  position: relative;
}

.evidence-image {
  display: block;
  user-select: none;
  -webkit-user-drag: none;
}

/* Fullscreen styles */
.image-container:fullscreen {
  max-height: 100vh;
  margin: 0;
  border: none;
  border-radius: 0;
  background-color: #000;
}

.image-container:fullscreen .image-wrapper {
  height: 100vh;
}

/* Responsive adjustments */
@media (max-width: 599px) {
  .image-container {
    max-height: 50vh;
    min-height: 300px;
    margin: 0 8px 8px;
  }
}

@media (min-width: 1280px) {
  .image-container {
    max-height: 80vh;
  }
}

/* Scrollbar styling for actual size mode */
.image-wrapper::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.image-wrapper::-webkit-scrollbar-track {
  background: rgba(var(--v-theme-surface-variant), 0.1);
  border-radius: 4px;
}

.image-wrapper::-webkit-scrollbar-thumb {
  background: rgba(var(--v-theme-outline), 0.3);
  border-radius: 4px;
}

.image-wrapper::-webkit-scrollbar-thumb:hover {
  background: rgba(var(--v-theme-outline), 0.5);
}
</style>
