<template>
  <v-dialog
    v-model="show"
    max-width="1200px"
    scrollable
    @update:model-value="handleModelValueUpdate"
  >
    <v-card class="d-flex flex-column h-100-dialog">
      <v-card-title class="d-flex align-center justify-space-between flex-shrink-0">
        <div class="d-flex align-center ga-2">
          <v-icon :icon="titleIcon" />
          <span>{{ titleText }}</span>
          <span v-if="evidenceItem?.title" class="text-caption text-medium-emphasis ml-2">
            ({{ evidenceItem.title }})
          </span>
        </div>
        <v-btn icon="mdi-close" size="small" variant="text" @click="show = false" />
      </v-card-title>

      <v-card-text class="pa-0 flex-grow-1 d-flex flex-column">
        <div v-if="loading" class="d-flex justify-center pa-8">
          <v-progress-circular :size="50" :width="6" color="primary" indeterminate />
        </div>

        <v-alert v-else-if="error" class="ma-4" type="error" variant="outlined">
          {{ error }}
        </v-alert>

        <div v-else-if="evidenceItem" class="flex-grow-1 d-flex flex-column">
          <TextContentPreview
            v-if="displayContentType === 'TEXT'"
            :content="fileContent"
            :file-info="fileInfo"
            ref="contentPreviewRef"
          />
          <ImageContentPreview
            v-else-if="displayContentType === 'IMAGE'"
            :evidence-item="evidenceItem"
            :file-info="fileInfo"
            :image-data-url="fileContent"
            ref="contentPreviewRef"
          />
          <v-alert v-else type="info" class="ma-4" variant="outlined">
            Unsupported file type for preview.
          </v-alert>
        </div>
      </v-card-text>

      <v-card-actions class="flex-shrink-0">
        <v-spacer />
        <v-btn color="primary" variant="text" @click="show = false"> Close </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue';
import { evidenceService } from '@/services/evidence';
import {
  FileTypeIcons,
  getFileTypeByExtension,
  getFileTypeByMime,
  SUPPORTED_PREVIEW_TYPES
} from '@/utils/fileExtension.js'
import TextContentPreview from './file-previews/TextContentPreview.vue';
import ImageContentPreview from './file-previews/ImageContentPreview.vue';

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  evidenceItem: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(['update:modelValue']);

const show = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

const loading = ref(false);
const error = ref('');
const fileContent = ref(null);
const fileInfo = ref(null);
const contentPreviewRef = ref(null);

// This computed property determines the *initial* request strategy (extension-based)
const requestContentType = computed(() => {
  if (!props.evidenceItem) return null;
  const fileExtension = props.evidenceItem.title.split('.').pop();
  return getFileTypeByExtension(fileExtension);
});

// This computed property determines the *actual display type* (MIME-type preferred)
const displayContentType = computed(() => {
  if (fileInfo.value && fileInfo.value.mime_type) {
    const mimeTypeGroup = getFileTypeByMime(fileInfo.value.mime_type);
    if (SUPPORTED_PREVIEW_TYPES.includes(mimeTypeGroup)) {
      return mimeTypeGroup;
    }
  }
  if (SUPPORTED_PREVIEW_TYPES.includes(requestContentType.value)) {
    return requestContentType.value;
  }
  return 'DEFAULT';
});

const titleIcon = computed(() => {
  return FileTypeIcons[displayContentType.value] || FileTypeIcons.DEFAULT;
});

const titleText = computed(() => {
  switch (displayContentType.value) {
    case 'TEXT':
      return 'Text File Content';
    case 'IMAGE':
      return 'Image Preview';
    case 'PDF':
      return 'PDF Document Preview';
    // Add more cases for other types
    default:
      return 'File Content';
  }
});

const cleanupBlobUrl = () => {
  if (fileContent.value && typeof fileContent.value === 'string' && fileContent.value.startsWith('blob:')) {
    URL.revokeObjectURL(fileContent.value);
    fileContent.value = null;
  }
};

const fetchFileContent = async (item) => {
  if (!item || !item.id) {
    cleanupBlobUrl();
    fileContent.value = null;
    fileInfo.value = null;
    error.value = '';
    return;
  }

  // Determine the content type *for the request*
  const currentRequestType = requestContentType.value;

  loading.value = true;
  error.value = '';
  cleanupBlobUrl();
  fileContent.value = null;
  fileInfo.value = null;

  try {
    if (currentRequestType === 'TEXT') {
      const { content, file_info: info } = await evidenceService.getEvidenceContent(item.id);
      fileInfo.value = info;
      fileContent.value = content;
    } else if (currentRequestType === 'IMAGE') {
      const fileBlob = await evidenceService.downloadEvidence(item.id);

      fileContent.value = URL.createObjectURL(fileBlob);

      fileInfo.value = {
        filename: item.title,
        file_size: item.size || fileBlob.size,
        mime_type: fileBlob.type,
      };

    } else {
      error.value = 'This file type is not supported for content viewing.';
    }
  } catch (err) {
    console.error('Error fetching file content:', err);
    if (err.response && err.response.data && err.response.data.detail) {
      error.value = err.response.data.detail;
    } else {
      error.value = 'Failed to load file content.';
    }
    cleanupBlobUrl();
  } finally {
    loading.value = false;
  }
};

const resetModalState = () => {
  if (contentPreviewRef.value && typeof contentPreviewRef.value.reset === 'function') {
    contentPreviewRef.value.reset();
  }

  loading.value = false;
  error.value = '';
  cleanupBlobUrl();
  fileInfo.value = null;
};

watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue && props.evidenceItem) {
      fetchFileContent(props.evidenceItem);
    } else if (!newValue) {
      resetModalState();
    }
  },
  { immediate: true }
);

watch(
  () => props.evidenceItem,
  (newItem, oldItem) => {
    if (show.value && newItem && newItem.id !== oldItem?.id) {
      fetchFileContent(newItem);
    }
  },
);

const handleModelValueUpdate = (value) => {
  emit('update:modelValue', value);
  if (!value) {
    resetModalState();
  }
};

onUnmounted(() => {
  cleanupBlobUrl();
});
</script>

<style scoped>
.h-100-dialog {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.v-card-text {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}
</style>
