<template>
  <div v-if="show" class="fixed inset-0 z-10 overflow-y-auto">
    <div class="flex min-h-screen items-center justify-center px-4 pt-4 pb-20 text-center sm:block sm:p-0">
      <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" @click="$emit('close')" />

      <div class="inline-block transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 px-4 pt-5 pb-4 text-left align-bottom shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6 sm:align-middle">
        <div class="absolute top-0 right-0 pt-4 pr-4">
          <button
            type="button"
            class="rounded-md bg-white dark:bg-gray-800 text-gray-400 hover:text-gray-500 focus:outline-none"
            @click="$emit('close')"
          >
            <span class="sr-only">Close</span>
            <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="sm:flex sm:items-start">
          <div class="mt-3 w-full text-center sm:mt-0 sm:text-left">
            <h3 class="text-lg font-medium leading-6 text-gray-900 dark:text-gray-100">
              Upload Evidence
            </h3>

            <form @submit.prevent="handleSubmit" class="mt-4 space-y-4">
              <div>
                <label for="category" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Category
                </label>
                <select
                  id="category"
                  v-model="form.category"
                  class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-500 focus:ring-cyan-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white sm:text-sm"
                >
                  <option v-for="category in CATEGORIES" :key="category" :value="category">
                    {{ category }}
                  </option>
                </select>
              </div>

              <div>
                <label for="description" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Description (Optional)
                </label>
                <textarea
                  id="description"
                  v-model="form.description"
                  rows="3"
                  class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-500 focus:ring-cyan-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white sm:text-sm"
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
                          <button
                            @click="removeFile(file)"
                            class="ml-2 text-cyan-600 hover:text-cyan-500"
                          >
                            Remove
                          </button>
                        </li>
                      </ul>
                      <button
                        v-if="selectedFiles.length > 1"
                        @click="clearFiles"
                        class="mt-2 text-sm text-cyan-600 hover:text-cyan-500"
                      >
                        Remove All
                      </button>
                    </div>
                    <div v-if="fileError" class="mt-2">
                      <p class="text-sm text-red-600">
                        {{ fileError }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div class="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                <button
                  type="submit"
                  :disabled="uploading || selectedFiles.length === 0"
                  class="inline-flex w-full justify-center rounded-md border border-transparent bg-cyan-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed sm:ml-3 sm:w-auto sm:text-sm"
                >
                  {{ uploading ? 'Uploading...' : 'Upload' }}
                </button>
                <button
                  type="button"
                  class="mt-3 inline-flex w-full justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-base font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 sm:mt-0 sm:w-auto sm:text-sm"
                  @click="$emit('close')"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits } from 'vue';
import { evidenceService } from '../services/evidence';

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
  } catch (error) {
    fileError.value = 'Failed to upload files. Please try again.';
  } finally {
    uploading.value = false;
  }
}
</script>
