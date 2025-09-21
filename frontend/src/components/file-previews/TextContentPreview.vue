<template>
  <div class="d-flex flex-column h-100">
    <v-card v-if="fileInfo" class="ma-4 mb-2 flex-shrink-0" variant="outlined">
      <v-card-text class="py-3">
        <v-row dense align="center">
          <v-col cols="12" sm="6" md="3">
            <div class="text-caption text-medium-emphasis">File</div>
            <div class="text-body-2 font-weight-medium">{{ fileInfo.filename }}</div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <div class="text-caption text-medium-emphasis">Size</div>
            <div class="text-body-2 font-weight-medium">
              {{ formatFileSize(fileInfo.file_size) }}
            </div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <div class="text-caption text-medium-emphasis">Lines</div>
            <div class="text-body-2 font-weight-medium">
              {{ fileInfo.line_count?.toLocaleString() }}
            </div>
          </v-col>
          <v-col cols="12" sm="6" md="2">
            <div class="text-caption text-medium-emphasis">Characters</div>
            <div class="text-body-2 font-weight-medium">
              {{ fileInfo.char_count?.toLocaleString() }}
            </div>
          </v-col>
          <v-col cols="12" md="3" class="d-flex justify-end ga-2">
            <v-btn
              size="small"
              variant="outlined"
              prepend-icon="mdi-content-copy"
              @click="copyToClipboard"
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
        variant="outlined"
        density="compact"
        prepend-inner-icon="mdi-magnify"
        clearable
        hide-details
        @input="highlightSearch"
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

const copyToClipboard = async () => {
  try {
    await navigator.clipboard.writeText(props.content)
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}

watch(
  () => props.content,
  () => {
    highlightSearch()
  },
  { immediate: true },
)

watch(searchTerm, () => {
  highlightSearch()
})

const reset = () => {
  searchTerm.value = '';
  wordWrap.value = false;
};

defineExpose({ reset });
</script>

<style scoped>
.h-100 {
  height: 100%;
}
.content-container {
  max-height: 60vh;
  overflow: auto;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
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
  background-color: rgba(var(--v-theme-surface-variant), 0.05);
  min-height: 100%;
}

.content-display.word-wrap {
  white-space: pre-wrap;
  word-break: break-word;
}

:deep(mark) {
  background-color: rgb(var(--v-theme-warning));
  color: rgb(var(--v-theme-on-warning));
  padding: 2px 4px;
  border-radius: 4px;
  font-weight: bold;
}

@media (max-width: 599px) {
  .content-container {
    max-height: 50vh;
    margin: 0 8px 8px;
  }

  .content-display {
    padding: 12px;
    font-size: 12px;
  }
}

@media (min-width: 1280px) {
  .content-container {
    max-height: 70vh;
  }
}

.content-container::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.content-container::-webkit-scrollbar-track {
  background: rgba(var(--v-theme-surface-variant), 0.1);
  border-radius: 4px;
}

.content-container::-webkit-scrollbar-thumb {
  background: rgba(var(--v-theme-outline), 0.3);
  border-radius: 4px;
}

.content-container::-webkit-scrollbar-thumb:hover {
  background: rgba(var(--v-theme-outline), 0.5);
}
</style>
