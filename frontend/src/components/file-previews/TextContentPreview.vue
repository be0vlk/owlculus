<template>
  <div class="d-flex flex-column h-100">
    <v-card v-if="fileInfo" class="ma-4 mb-2 flex-shrink-0" variant="outlined">
      <v-card-text class="py-3">
        <v-row class="align-center" density="compact">
          <v-col cols="12" sm="6" md="3">
            <div class="text-body-small text-medium-emphasis">File</div>
            <div class="text-body-medium font-weight-medium">{{ fileInfo.filename }}</div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <div class="text-body-small text-medium-emphasis">Size</div>
            <div class="text-body-medium font-weight-medium">
              {{ formatFileSize(fileInfo.file_size) }}
            </div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <div class="text-body-small text-medium-emphasis">Lines</div>
            <div class="text-body-medium font-weight-medium">
              {{ fileInfo.line_count?.toLocaleString() }}
            </div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <div class="text-body-small text-medium-emphasis">Characters</div>
            <div class="text-body-medium font-weight-medium">
              {{ fileInfo.char_count?.toLocaleString() }}
            </div>
          </v-col>
          <v-col cols="12" md="3" class="d-flex justify-end ga-2">
            <v-btn
              size="small"
              variant="outlined"
              prepend-icon="mdi-content-copy"
              @click="copyToClipboard(content)"
            >
              Copy All
            </v-btn>
            <v-btn
              size="small"
              variant="outlined"
              prepend-icon="mdi-wrap"
              @click="wordWrap = !wordWrap"
              :color="wordWrap ? 'primary' : ''"
            >
              Wrap
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <div class="mx-4 mb-2 flex-shrink-0">
      <v-text-field
        v-model="searchTerm"
        label="Search in file"
        density="compact"
        prepend-inner-icon="mdi-magnify"
        clearable
        hide-details
      />
    </div>

    <div class="content-container flex-grow-1">
      <pre
        ref="contentElement"
        class="content-display"
        :class="{ 'word-wrap': wordWrap }"
        v-html="displayContent"
      ></pre>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { copyToClipboard } from '@/utils/clipboard'
import { formatFileSize } from '@/utils/huntDisplayUtils'

const props = defineProps({
  content: {
    type: String,
    default: '',
  },
  fileInfo: {
    type: Object,
    default: null,
  },
})

const searchTerm = ref('')
const wordWrap = ref(false)
const contentElement = ref(null)
const displayContent = ref('')

const escapeHtml = (text) => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

const highlightSearch = () => {
  if (!props.content) {
    displayContent.value = ''
    return
  }

  let content = escapeHtml(props.content)

  if (searchTerm.value && searchTerm.value.length > 0) {
    const searchRegex = new RegExp(`(${escapeHtml(searchTerm.value)})`, 'gi')
    content = content.replace(searchRegex, '<mark>$1</mark>')
  }

  displayContent.value = content

  if (searchTerm.value) {
    nextTick(() => {
      const firstMatch = contentElement.value?.querySelector('mark')
      if (firstMatch) {
        firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }
}

watch([() => props.content, searchTerm], highlightSearch, { immediate: true })

const reset = () => {
  searchTerm.value = ''
  wordWrap.value = false
}

defineExpose({ reset })
</script>

<style scoped>
.content-container {
  max-height: 60vh;
  overflow: auto;
  scrollbar-width: thin;
  border: 1px solid rgb(var(--v-theme-outline), 0.2);
  margin: 0 16px 16px;
  border-radius: 8px;
}

.content-display {
  margin: 0;
  padding: 16px;
  font-family: 'Courier New', Monaco, monospace;
  font-size: 14px;
  line-height: 1.4;
  white-space: pre;
  overflow-x: auto;
  background-color: rgb(var(--v-theme-surface-variant), 0.05);
  min-height: 100%;
}

.content-display.word-wrap {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

:deep(mark) {
  background-color: rgb(var(--v-theme-warning));
  color: rgb(var(--v-theme-on-warning));
  padding: 2px 4px;
  border-radius: 4px;
  font-weight: bold;
}

@media (width <= 599px) {
  .content-container {
    max-height: 50vh;
    margin: 0 8px 8px;
  }

  .content-display {
    padding: 12px;
    font-size: 12px;
  }
}

@media (width >= 1280px) {
  .content-container {
    max-height: 70vh;
  }
}
</style>
