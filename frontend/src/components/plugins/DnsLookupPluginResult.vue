<template>
  <div class="space-y-4">
    <template v-for="(resultItem, index) in normalizedResult" :key="index">
      <!-- Domain Header -->
      <div class="bg-gray-50 dark:bg-gray-700 shadow rounded-lg p-4">
        <div class="flex items-center">
          <svg class="w-5 h-5 mr-2 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
          </svg>
          <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-100">
            {{ resultItem.domain }}
          </h3>
        </div>
      </div>

      <!-- IP Addresses -->
      <div v-if="hasIpAddresses(resultItem)" class="mt-4">
        <h4 class="text-sm font-medium text-gray-800 dark:text-gray-100 flex items-center mb-2">
          <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          IP Addresses
        </h4>
        <div class="bg-white dark:bg-gray-800 shadow rounded-lg divide-y divide-gray-200 dark:divide-gray-700">
          <div class="p-4">
            <div class="flex justify-between items-start">
              <code class="text-sm font-mono text-gray-800 dark:text-gray-100 whitespace-pre-wrap">{{ resultItem.ips.join('\n') }}</code>
              <button @click="copyToClipboard(resultItem.ips.join('\n'))"
                      class="ml-3 p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors flex-shrink-0"
                      title="Copy all IP addresses">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- No Results -->
      <div v-else class="mt-4 bg-gray-50 dark:bg-gray-700 shadow rounded-lg p-4">
        <p class="text-gray-800 dark:text-gray-100 text-sm">
          No IP addresses found for this domain.
        </p>
      </div>
    </template>

    <!-- No Results at all -->
    <div v-if="!result || normalizedResult.length === 0" class="bg-gray-50 dark:bg-gray-700 shadow rounded-lg p-4 text-center">
      <p class="text-gray-800 dark:text-gray-100 text-sm">
        No results available.
      </p>
    </div>
  </div>
</template>

<script setup>
import { defineProps, computed } from 'vue';

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  }
});

const normalizedResult = computed(() => {
  if (!props.result) return [];
  return Array.isArray(props.result) ? props.result : [props.result];
});

const hasIpAddresses = (result) => {
  return result && 
         !result.error &&
         Array.isArray(result.ips) && 
         result.ips.length > 0;
};

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    console.error('Failed to copy text:', err);
  }
};
</script>

<style scoped>
</style>
