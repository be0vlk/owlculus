<template>
  <div class="d-flex flex-column h-100">
    <v-card v-if="fileInfo" class="ma-4 mb-2 flex-shrink-0" variant="outlined">
      <v-card-text class="py-3">
        <v-row class="align-center" density="compact">
          <v-col cols="12" sm="6" md="3">
            <div class="text-body-small text-medium-emphasis">File</div>
            <div class="text-body-medium font-weight-medium">
              {{ fileInfo.filename || evidenceItem?.title }}
            </div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <div class="text-body-small text-medium-emphasis">Size</div>
            <div class="text-body-medium font-weight-medium">
              {{ formatFileSize(fileInfo.file_size) }}
            </div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <div class="text-body-small text-medium-emphasis">Dimensions</div>
            <div class="text-body-medium font-weight-medium">{{ imageDimensions }}</div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <div class="text-body-small text-medium-emphasis">Format</div>
            <div class="text-body-medium font-weight-medium">{{ imageFormat }}</div>
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

    <div class="mx-4 mb-2 flex-shrink-0 d-flex flex-wrap align-center ga-2">
      <v-btn
        size="small"
        icon="mdi-magnify-minus"
        aria-label="Zoom out"
        variant="outlined"
        @click="zoomOut"
        :disabled="zoomLevel <= 0.25"
      />
      <v-chip size="small" variant="outlined"> {{ Math.round(zoomLevel * 100) }}% </v-chip>
      <v-btn
        size="small"
        icon="mdi-magnify-plus"
        aria-label="Zoom in"
        variant="outlined"
        @click="zoomIn"
        :disabled="zoomLevel >= 3"
      />
      <v-btn size="small" variant="outlined" @click="resetZoom"> Reset </v-btn>
      <v-spacer />
      <v-btn-toggle v-model="fitMode" density="compact" mandatory variant="outlined">
        <v-btn aria-label="Fit to screen" value="contain" size="small">
          <v-icon>mdi-fit-to-screen-outline</v-icon>
          <v-tooltip activator="parent" location="top">Fit to screen</v-tooltip>
        </v-btn>
        <v-btn aria-label="Actual size" value="actual" size="small">
          <v-icon>mdi-image-size-select-actual</v-icon>
          <v-tooltip activator="parent" location="top">Actual size</v-tooltip>
        </v-btn>
      </v-btn-toggle>
    </div>

    <div ref="imageContainer" class="image-container flex-grow-1" @wheel.prevent="handleWheel">
      <div class="image-wrapper" :class="fitMode === 'contain' ? 'fit-contain' : 'overflow-auto'">
        <img
          :src="imageDataUrl"
          :alt="evidenceItem?.title || 'Evidence image'"
          class="evidence-image"
          :style="{ transform: `scale(${zoomLevel})` }"
          @load="handleImageLoad"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { evidenceService } from '@/services/evidence.js'
import { downloadBlob } from '@/utils/download'
import { formatFileSize } from '@/utils/huntDisplayUtils'

const props = defineProps({
  evidenceItem: {
    type: Object,
    default: null,
  },
  fileInfo: {
    type: Object,
    default: null,
  },
  // Blob URL owned (and revoked) by FileContentModal.
  imageDataUrl: {
    type: String,
    default: '',
  },
})

const zoomLevel = ref(1)
const fitMode = ref('contain')
const imageDimensions = ref('')
const imageContainer = ref(null)

const imageFormat = computed(
  () => props.evidenceItem?.title?.split('.').pop()?.toUpperCase() || 'Unknown',
)

const handleImageLoad = (event) => {
  imageDimensions.value = `${event.target.naturalWidth} × ${event.target.naturalHeight}`
}

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

const downloadImage = async () => {
  if (!props.evidenceItem) return

  try {
    const download = await evidenceService.downloadEvidence(props.evidenceItem.id)
    downloadBlob(download, props.evidenceItem.title)
  } catch (err) {
    console.error('Failed to download image:', err)
  }
}

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

const reset = () => {
  zoomLevel.value = 1
  fitMode.value = 'contain'
  imageDimensions.value = ''
}

defineExpose({ reset })
</script>

<style scoped>
.image-container {
  max-height: 70vh;
  min-height: 400px;
  border: 1px solid rgb(var(--v-theme-outline), 0.2);
  margin: 0 16px 16px;
  border-radius: 8px;
  background-color: rgb(var(--v-theme-surface-variant), 0.05);
  overflow: hidden;
  position: relative;
}

.image-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  scrollbar-width: thin;
}

.evidence-image {
  display: block;
  user-select: none;
  -webkit-user-drag: none;
  object-fit: contain;
  transition: transform 0.2s ease;
}

.fit-contain .evidence-image {
  max-width: 100%;
  max-height: 100%;
}

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

@media (width <= 599px) {
  .image-container {
    max-height: 50vh;
    min-height: 300px;
    margin: 0 8px 8px;
  }
}

@media (width >= 1280px) {
  .image-container {
    max-height: 80vh;
  }
}
</style>
