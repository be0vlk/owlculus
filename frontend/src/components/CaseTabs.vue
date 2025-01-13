<template>
    <div class="sm:hidden">
      <label for="tabs" class="sr-only">Select a tab</label>
      <select
        id="tabs"
        name="tabs"
        class="block w-full focus:ring-cyan-500 focus:border-cyan-500 border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        v-model="activeTab"
      >
        <option v-for="tab in tabs" :key="tab.name" :value="tab.name">
          {{ tab.label }}
        </option>
      </select>
    </div>
    <div class="hidden sm:block">
      <div class="border-b border-gray-200 dark:border-gray-700">
        <nav class="-mb-px flex space-x-8" aria-label="Tabs">
          <button
            v-for="tab in tabs"
            :key="tab.name"
            @click="activeTab = tab.name"
            :class="[
              activeTab === tab.name
                ? 'border-cyan-500 text-cyan-600 dark:text-cyan-400 dark:border-cyan-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300 dark:hover:border-gray-300',
              'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm',
            ]"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>
    </div>
    <div class="mt-4">
      <slot :active-tab="activeTab" />
    </div>
  </template>
  
  <script setup>
  import { ref } from 'vue';
  
  const props = defineProps({
    tabs: {
      type: Array,
      required: true,
      default: () => [],
    },
  });
  
  const activeTab = ref(props.tabs[0]?.name);
  </script>