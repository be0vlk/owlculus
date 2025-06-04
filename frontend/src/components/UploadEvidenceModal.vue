<template>
  <v-dialog v-model="dialogVisible" max-width="600px" persistent>

    <v-card>
      <v-card-title>
        <span class="text-h5">Upload Evidence</span>
      </v-card-title>
      <v-card-text>
        <v-form @submit.prevent="handleSubmit">
      <div>
        <label for="category" class="block text-sm font-medium mb-1">
          Category
        </label>
        <v-select
          id="category"
          v-model="form.category"
          :items="CATEGORIES"
          variant="outlined"
          density="comfortable"
        />
      </div>

      <div>
        <label for="description" class="block text-sm font-medium mb-1">
          Description (Optional)
        </label>
        <v-textarea
          id="description"
          v-model="form.description"
          rows="3"
          variant="outlined"
          density="comfortable"
        />
      </div>

              <div>
                <div 
                  class="mt-1 flex justify-center rounded-md border-2 border-dashed border-gray-300 dark:border-gray-600 px-6 pt-5 pb-6"
                  @dragover.prevent
                  @drop.prevent="handleFileDrop"
                >
                  <div class="space-y-1 text-center">
                    <svg
                      class="mx-auto h-12 w-12 text-gray-400"
                      stroke="currentColor"
                      fill="none"
                      viewBox="0 0 48 48"
                      aria-hidden="true"
                    >
                      <path
                        d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                    <div class="flex text-sm text-gray-600 dark:text-gray-400">
                      <label
                        for="file-upload"
                        class="relative cursor-pointer rounded-md bg-white dark:bg-gray-800 font-medium text-cyan-600 focus-within:outline-none focus-within:ring-2 focus-within:ring-cyan-500 focus-within:ring-offset-2 hover:text-cyan-500"
                      >
                        <span>Upload a file</span>
                        <input
                          id="file-upload"
                          type="file"
                          class="sr-only"
                          @change="handleFileSelect"
                          accept="image/*,application/pdf,.doc,.docx,.txt"
                          multiple
                        >
                      </label>
                      <p class="pl-1">or drag and drop</p>
                    </div>
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                      Images, PDF, DOC, DOCX or TXT up to 50MB
                    </p>
                    <div v-if="selectedFiles.length > 0" class="mt-2">
                      <p class="text-sm text-gray-500 dark:text-gray-400">
                        Selected {{ selectedFiles.length }} file(s):
                      </p>
                      <ul class="mt-1 space-y-1">
                        <li v-for="file in selectedFiles" :key="file.name" class="flex items-center">
                          <span class="text-sm text-gray-500 dark:text-gray-400">{{ file.name }}</span>
                          <v-btn
                            size="small"
                            variant="text"
                            @click="removeFile(file)"
                            class="ml-2"
                          >
                            Remove
                          </v-btn>
                        </li>
                      </ul>
                      <v-btn
                        v-if="selectedFiles.length > 1"
                        size="small"
                        variant="text"
                        @click="clearFiles"
                        class="mt-2"
                      >
                        Remove All
                      </v-btn>
                    </div>
                    <div v-if="fileError" class="mt-2">
                      <p class="text-sm text-red-600">
                        {{ fileError }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="$emit('close')"
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
          {{ uploading ? 'Uploading...' : 'Upload' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, defineProps, defineEmits, computed } from 'vue';
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
  category: 'Other',
});

const selectedFiles = ref([]);
const uploading = ref(false);
const fileError = ref(null);

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
    const evidence = await evidenceService.createEvidence({
      description: form.value.description,
      category: form.value.category,
      caseId: props.caseId,
      files: selectedFiles.value
    });
    emit('uploaded', evidence);
    emit('close');
  } catch {
    fileError.value = 'Failed to upload files. Please try again.';
  } finally {
    uploading.value = false;
  }
}
</script>
