<template>
    <li class="py-4">
      <div class="flex items-center space-x-4">
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-900 truncate dark:text-white">
            <slot name="name" />
          </p>
          <p v-if="hasDetail" class="text-sm text-gray-500 truncate dark:text-gray-400">
            <slot name="detail" />
          </p>
        </div>
        <div>
          <button
            @click="$emit('viewDetails')"
            class="inline-flex items-center shadow-sm px-2.5 py-0.5 border border-gray-300 dark:border-gray-700 rounded-md text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500"
          >
            View Details
          </button>
        </div>
      </div>
    </li>
  </template>
  
  <script setup>
  const props = defineProps({
      hasDetail: {
          type: Boolean,
          default: false
      }
  })
  
  defineEmits(['viewDetails']);
  </script>