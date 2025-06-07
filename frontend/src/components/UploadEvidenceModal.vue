<template>
  <v-dialog v-model="dialogVisible" max-width="600px" persistent>
    <v-card prepend-icon="mdi-cloud-upload" title="Upload Evidence">
      <v-card-text>
        <v-form ref="formRef" @submit.prevent="handleSubmit">
          <!-- Target Folder Alert -->
          <v-alert
            v-if="targetFolder"
            type="info"
            variant="tonal"
            class="mb-4"
            icon="mdi-folder"
          >
            Uploading to: <strong>{{ targetFolder.title }}</strong>
          </v-alert>

          <!-- Destination Folder Selection -->
          <v-select
            v-if="!targetFolder"
            v-model="selectedFolder"
            :items="folderOptions"
            item-title="label"
            item-value="value"
            label="Destination Folder"
            variant="outlined"
            density="comfortable"
            placeholder="Select a folder or upload to root"
            clearable
            class="mb-4"
          >
            <template v-slot:prepend-item>
              <v-list-item
                title="📁 Root (No folder)"
                @click="selectedFolder = null"
              />
              <v-divider />
            </template>
          </v-select>

          <!-- Category Selection -->
          <v-select
            v-model="form.category"
            :items="CATEGORIES"
            label="Category (Optional)"
            variant="outlined"
            density="comfortable"
            placeholder="Select a category"
            clearable
            class="mb-4"
          />

          <!-- Description -->
          <v-textarea
            v-model="form.description"
            label="Description (Optional)"
            rows="3"
            variant="outlined"
            density="comfortable"
            class="mb-4"
          />

          <!-- File Upload Area -->
          <v-card
            variant="outlined"
            class="upload-area mb-4"
            :class="{ 'drag-over': isDragOver }"
            @dragover.prevent="isDragOver = true"
            @dragleave.prevent="isDragOver = false"
            @drop.prevent="handleFileDrop"
          >
            <v-card-text class="text-center pa-8">
              <v-icon 
                size="64" 
                color="primary" 
                class="mb-4"
              >
                mdi-cloud-upload-outline
              </v-icon>
              
              <div class="text-h6 mb-2">Drop files here or browse</div>
              
              <v-btn
                color="primary"
                variant="outlined"
                class="mb-4"
                @click="$refs.fileInput.click()"
              >
                <v-icon start>mdi-file-plus</v-icon>
                Choose Files
              </v-btn>
              
              <input
                ref="fileInput"
                type="file"
                class="d-none"
                @change="handleFileSelect"
                accept="image/*,application/pdf,.doc,.docx,.txt"
                multiple
              >
              
              <div class="text-body-2 text-medium-emphasis">
                Images, PDF, DOC, DOCX or TXT up to 50MB
              </div>
            </v-card-text>
          </v-card>

          <!-- Selected Files Display -->
          <v-card v-if="selectedFiles.length > 0" variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1">
              Selected Files ({{ selectedFiles.length }})
              <v-spacer />
              <v-btn
                size="small"
                variant="text"
                color="error"
                @click="clearFiles"
              >
                <v-icon start>mdi-delete</v-icon>
                Clear All
              </v-btn>
            </v-card-title>
            
            <v-divider />
            
            <v-list density="compact">
              <v-list-item
                v-for="file in selectedFiles"
                :key="file.name"
                :title="file.name"
                :subtitle="`${(file.size / 1024 / 1024).toFixed(2)} MB`"
              >
                <template v-slot:prepend>
                  <v-icon>{{ getFileIcon(file.name) }}</v-icon>
                </template>
                
                <template v-slot:append>
                  <v-btn
                    size="small"
                    variant="text"
                    color="error"
                    icon="mdi-close"
                    @click="removeFile(file)"
                  />
                </template>
              </v-list-item>
            </v-list>
          </v-card>

          <!-- Error Display -->
          <v-alert
            v-if="fileError"
            type="error"
            variant="tonal"
            class="mb-4"
          >
            {{ fileError }}
          </v-alert>
        </v-form>
      </v-card-text>

      <v-divider />

      <v-card-actions>
        <v-spacer />
        <v-btn
          variant="text"
          @click="$emit('close')"
          :disabled="uploading"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="handleSubmit"
          :disabled="uploading || selectedFiles.length === 0"
          :loading="uploading"
        >
          Upload
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, defineProps, defineEmits, computed, watch, onMounted } from 'vue';
import { evidenceService } from '../services/evidence';
// Vuetify components are auto-imported

const CATEGORIES = [
  'Social Media',
  'Associates',
  'Network Assets',
  'Communications',
  'Documents',
  'Other'
];

const props = defineProps({
  show: {
    type: Boolean,
    required: true,
  },
  caseId: {
    type: Number,
    required: true,
  },
  targetFolder: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(['close', 'uploaded']);

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
});

const form = ref({
  description: '',
  category: '',
});

const selectedFiles = ref([]);
const uploading = ref(false);
const fileError = ref(null);
const selectedFolder = ref(null);
const availableFolders = ref([]);
const loadingFolders = ref(false);
const isDragOver = ref(false);
const formRef = ref(null);

// Computed properties
const folderOptions = computed(() => {
  const buildFolderTree = (folders, parentId = null, prefix = '') => {
    const options = []
    const children = folders.filter(f => f.parent_folder_id === parentId && f.is_folder)
    
    children.forEach(folder => {
      const label = prefix + '📁 ' + folder.title
      options.push({
        label,
        value: folder,
        folder
      })
      
      // Add nested folders with indentation
      const nestedOptions = buildFolderTree(folders, folder.id, prefix + '  ')
      options.push(...nestedOptions)
    })
    
    return options
  }
  
  return buildFolderTree(availableFolders.value)
})

// Methods
const loadFolders = async () => {
  if (!props.caseId) return
  
  try {
    loadingFolders.value = true
    const folders = await evidenceService.getFolderTree(props.caseId)
    availableFolders.value = folders
  } catch (error) {
    console.error('Failed to load folders:', error)
  } finally {
    loadingFolders.value = false
  }
}

function handleFileSelect(event) {
  const files = Array.from(event.target.files);
  const invalidFiles = files.filter(file => file.size > 50000000);
  
  if (invalidFiles.length > 0) {
    fileError.value = `${invalidFiles.length} file(s) exceed 50MB size limit`;
    return;
  }

  selectedFiles.value = [...selectedFiles.value, ...files];
  fileError.value = null;
}

function handleFileDrop(event) {
  isDragOver.value = false;
  const files = Array.from(event.dataTransfer.files);
  const invalidFiles = files.filter(file => file.size > 50000000);
  
  if (invalidFiles.length > 0) {
    fileError.value = `${invalidFiles.length} file(s) exceed 50MB size limit`;
    return;
  }

  selectedFiles.value = [...selectedFiles.value, ...files];
  fileError.value = null;
}

function removeFile(file) {
  selectedFiles.value = selectedFiles.value.filter(f => f !== file);
}

function clearFiles() {
  selectedFiles.value = [];
  fileError.value = null;
}

async function handleSubmit() {
  if (selectedFiles.value.length === 0) {
    fileError.value = 'Please select at least one file';
    return;
  }

  try {
    uploading.value = true;
    
    // Determine target folder - either from prop (context menu) or user selection
    const targetFolderData = props.targetFolder || selectedFolder.value;
    
    const evidence = await evidenceService.createEvidence({
      description: form.value.description,
      category: form.value.category || 'Other',
      caseId: props.caseId,
      files: selectedFiles.value,
      folderPath: targetFolderData?.folder_path,
      parentFolderId: targetFolderData?.id
    });
    emit('uploaded', evidence);
    emit('close');
  } catch {
    fileError.value = 'Failed to upload files. Please try again.';
  } finally {
    uploading.value = false;
  }
}

// Watch for dialog opening to load folders
watch(() => props.show, (newShow) => {
  if (newShow && props.caseId) {
    loadFolders()
  }
})

// Load folders on mount if dialog is already open
onMounted(() => {
  if (props.show && props.caseId) {
    loadFolders()
  }
})

// Helper function to get appropriate file icon
function getFileIcon(fileName) {
  const extension = fileName.split('.').pop().toLowerCase();
  
  const iconMap = {
    pdf: 'mdi-file-pdf-box',
    doc: 'mdi-file-word-box',
    docx: 'mdi-file-word-box',
    txt: 'mdi-file-document-outline',
    jpg: 'mdi-file-image',
    jpeg: 'mdi-file-image',
    png: 'mdi-file-image',
    gif: 'mdi-file-image',
    webp: 'mdi-file-image',
    svg: 'mdi-file-image'
  };
  
  return iconMap[extension] || 'mdi-file-outline';
}
</script>

<style scoped>
.upload-area {
  transition: all 0.2s ease-in-out;
}

.upload-area.drag-over {
  border-color: rgb(var(--v-theme-primary));
  background-color: rgb(var(--v-theme-primary), 0.04);
}

.upload-area:hover {
  border-color: rgb(var(--v-theme-primary), 0.5);
}
</style>
