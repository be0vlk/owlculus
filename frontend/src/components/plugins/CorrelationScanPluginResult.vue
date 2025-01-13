<template>
  <div class="space-y-4">
    <template v-for="(resultItem, index) in normalizedResult" :key="index">
      <!-- Entity Match Card -->
      <div v-if="resultItem.type === 'data'" class="bg-gray-50 dark:bg-gray-700 shadow rounded-lg">
        <!-- Entity Header -->
        <div class="p-4 border-b border-gray-200 dark:border-gray-600">
          <div class="flex items-center">
            <svg class="w-5 h-5 mr-2 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-100">
              {{ resultItem.data.entity_name }}
            </h3>
            <span class="ml-2 px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded-full">
              {{ resultItem.data.entity_type }}
            </span>
            <span class="ml-2 px-2 py-1 text-xs font-medium" 
                  :class="{
                    'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200': resultItem.data.match_type === 'employer',
                    'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200': resultItem.data.match_type === 'name'
                  }">
              {{ resultItem.data.match_type === 'employer' ? 'Employer Match' : 'Name Match' }}
            </span>
          </div>
          
          <!-- Correlation Context -->
          <div class="mt-2 text-sm text-gray-600 dark:text-gray-400">
            <template v-if="resultItem.data.match_type === 'employer'">
              Found multiple people who work at <span class="font-medium">{{ resultItem.data.employer_name }}</span>.
              This employer connection may indicate a relationship between these cases.
            </template>
            <template v-else>
              Found an entity named <span class="font-medium">{{ resultItem.data.entity_name }}</span> that appears in multiple cases.
              This may indicate the same {{ resultItem.data.entity_type }} is involved in different investigations.
            </template>
          </div>
        </div>

        <!-- Matches List -->
        <div class="p-4">
          <div class="space-y-3">
            <div v-for="(match, matchIndex) in resultItem.data.matches" 
                 :key="matchIndex"
                 class="bg-white dark:bg-gray-800 shadow rounded-lg p-4">
              <div class="flex justify-between items-start">
                <div class="space-y-1">
                  <h4 class="text-sm font-semibold text-gray-800 dark:text-gray-100">
                    Case #{{ match.case_number }}
                  </h4>
                  <p class="text-sm text-gray-600 dark:text-gray-400">
                    {{ match.case_title }}
                  </p>
                  <template v-if="resultItem.data.match_type === 'employer' && match.person_name">
                    <p class="text-sm text-purple-600 dark:text-purple-400">
                      Person: {{ match.person_name }}
                    </p>
                  </template>
                </div>
                <a :href="'/case/' + match.case_id" 
                   class="flex items-center text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">
                  View Case
                  <svg class="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Error Message -->
      <div v-else-if="resultItem.type === 'error'"
           class="bg-red-50 dark:bg-red-900 border-l-4 border-red-400 p-4 rounded-lg">
        <div class="flex">
          <svg class="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p class="ml-3 text-sm text-red-700 dark:text-red-200">
            {{ resultItem.data.message }}
          </p>
        </div>
      </div>
    </template>

    <!-- No Results -->
    <div v-if="!result || normalizedResult.length === 0" class="bg-gray-50 dark:bg-gray-700 shadow rounded-lg p-4 text-center">
      <svg class="w-6 h-6 mx-auto text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
        No correlations found
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true
  }
})

const normalizedResult = computed(() => {
  if (!props.result) return [];
  return Array.isArray(props.result) ? props.result : [props.result];
})
</script>

<style scoped>
</style>
