<template>
  <div class="space-y-4">
    <div v-if="loading" class="flex justify-center">
      <LoadingSpinner size="medium" />
    </div>
    <div v-else-if="error" class="text-red-500 dark:text-red-400">
      {{ error }}
    </div>
    <div v-else class="border rounded-lg dark:border-gray-700">
      <div class="file-explorer">
        <template v-for="category in CATEGORIES" :key="category">
          <div class="directory-group">
            <div 
              @click="toggleDirectory(category)"
              class="flex items-center p-2 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
              :class="{'bg-gray-50 dark:bg-gray-800': expandedDirectories[category]}"
            >
              <span class="mr-2">
                <svg v-if="expandedDirectories[category]" class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
                <svg v-else class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </span>
              <svg class="w-5 h-5 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <span class="font-medium text-gray-700 dark:text-gray-300">{{ category }}</span>
              <span class="ml-2 text-sm text-gray-500">({{ groupedEvidence[category]?.length || 0 }} items)</span>
            </div>
            
            <transition name="slide">
              <ul v-if="expandedDirectories[category]" class="pl-8">
                <template v-if="groupedEvidence[category]?.length">
                  <li 
                    v-for="evidence in groupedEvidence[category]" 
                    :key="evidence.id"
                    class="flex items-center justify-between p-2 hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    <div class="flex items-center flex-1">
                      <svg v-if="evidence.evidence_type === 'file'" class="w-5 h-5 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                      <div>
                        <h3 class="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {{ evidence.title }}
                        </h3>
                        <p v-if="evidence.description" class="text-xs text-gray-500 dark:text-gray-400">
                          {{ evidence.description }}
                        </p>
                        <div class="text-xs text-gray-500 dark:text-gray-400">
                          Added {{ new Date(evidence.created_at).toLocaleString() }}
                        </div>
                      </div>
                    </div>
                    <div class="flex space-x-2 ml-4">
                      <button
                        v-if="evidence.evidence_type === 'file'"
                        @click="$emit('download', evidence)"
                        class="inline-flex items-center px-2 py-1 text-xs font-medium text-cyan-700 bg-cyan-100 rounded-md hover:bg-cyan-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 dark:bg-cyan-900 dark:text-cyan-100 dark:hover:bg-cyan-800"
                      >
                        Download
                      </button>
                      <button
                        @click="$emit('delete', evidence)"
                        class="inline-flex items-center px-2 py-1 text-xs font-medium text-red-700 bg-red-100 rounded-md hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 dark:bg-red-900 dark:text-red-100 dark:hover:bg-red-800"
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                </template>
                <li v-else class="py-8">
                  <div class="text-center text-gray-500 dark:text-gray-400">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                    </svg>
                    <h3 class="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">No evidence in this category</h3>
                    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Upload new evidence to get started</p>
                  </div>
                </li>
              </ul>
            </transition>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import LoadingSpinner from './LoadingSpinner.vue';

const props = defineProps({
  evidenceList: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
});

const expandedDirectories = ref({});

const CATEGORIES = [
  'Social Media',
  'Associates',
  'Network Assets',
  'Communications',
  'Documents',
  'Other'
];

const groupedEvidence = computed(() => {
  const groups = {};
  
  props.evidenceList.forEach(evidence => {
    const category = evidence.category || 'Other';
    if (!groups[category]) {
      groups[category] = [];
    }
    groups[category].push(evidence);
  });

  return groups;
});

const toggleDirectory = (category) => {
  expandedDirectories.value[category] = !expandedDirectories.value[category];
};

defineEmits(['download', 'delete']);
</script>

<style scoped>
.file-explorer {
  @apply divide-y divide-gray-200 dark:divide-gray-700;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
