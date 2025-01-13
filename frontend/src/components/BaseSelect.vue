<template>
    <div class="mb-4">
      <label :for="id" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
        {{ label }}
      </label>
      <select
        :id="id"
        :value="modelValue"
        @change="$emit('update:modelValue', $event.target.value)"
        class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm text-gray-900 bg-white dark:text-gray-100 dark:bg-gray-700 dark:border-gray-600"
      >
        <option v-for="option in options" :key="option.value" :value="option.value" class="text-gray-900 bg-white dark:text-gray-100 dark:bg-gray-700">
          {{ option.label }}
        </option>
      </select>
    </div>
  </template>
  
  <script setup>
  defineProps({
    label: { type: String, required: true },
    id: { type: String, required: true },
    modelValue: { type: String, default: '' },
    options: { type: Array, required: true },
  });
  
  defineEmits(['update:modelValue']);
  </script>