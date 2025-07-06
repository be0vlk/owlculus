<template>
  <v-dialog
    v-model="show"
    max-width="1200px"
    scrollable
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2">
          <v-icon icon="mdi-file-document-outline" />
          <span>Text File Content</span>
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

        <!-- Content Display -->
        <div v-else-if="content" class="d-flex flex-column">
          <!-- File Information Header -->
          <v-card v-if="fileInfo" class="ma-4 mb-2" variant="outlined">
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

          <!-- Search Bar -->
          <div class="mx-4 mb-2">
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

          <!-- Content Area -->
          <div class="content-container flex-grow-1">
            <pre
              ref="contentElement"
              class="content-display"
              :class="{ 'word-wrap': wordWrap }"
              v-html="displayContent"
            ></pre>
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
import { computed, ref, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  evidenceItem: {
    type: Object,
    default: null,
  },
  content: {
    type: String,
    default: '',
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
const searchTerm = ref('')
const wordWrap = ref(false)
const contentElement = ref(null)
const displayContent = ref('')

const show = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
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

// Escape HTML to prevent XSS
const escapeHtml = (text) => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// Highlight search terms in content
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

  // Scroll to first match if searching
  if (searchTerm.value) {
    nextTick(() => {
      const firstMatch = contentElement.value?.querySelector('mark')
      if (firstMatch) {
        firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }
}

// Copy content to clipboard
const copyToClipboard = async () => {
  try {
    await navigator.clipboard.writeText(props.content)
    // Could add toast notification here
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}

// Watch for content changes to update display
watch(
  () => props.content,
  () => {
    highlightSearch()
  },
  { immediate: true },
)

// Watch for search term changes
watch(searchTerm, () => {
  highlightSearch()
})

// Reset search when modal closes
watch(show, (newValue) => {
  if (!newValue) {
    searchTerm.value = ''
    wordWrap.value = false
  }
})
</script>

<style scoped>
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

/* Search highlighting */
:deep(mark) {
  background-color: rgb(var(--v-theme-warning));
  color: rgb(var(--v-theme-on-warning));
  padding: 2px 4px;
  border-radius: 4px;
  font-weight: bold;
}

/* Responsive adjustments */
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

/* Scrollbar styling */
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
