<template>
  <div class="mb-4">
    <label :for="id" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
      {{ label }}
    </label>
    <div class="mt-1">
      <input
        type="text"
        :id="id"
        :value="inputValue"
        @input="handleInput"
        @keydown.enter.prevent="addItem"
        class="block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm text-gray-900 bg-white dark:text-gray-100 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400"
        :placeholder="placeholder"
      />
      <div v-if="modelValue.length > 0" class="mt-2 space-y-2">
        <div v-for="(item, index) in modelValue" :key="index" 
             class="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded">
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ item }}</span>
          <button @click="removeItem(index)" 
                  class="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  label: { type: String, required: true },
  id: { type: String, required: true },
  modelValue: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Type and press Enter to add' },
});

const emit = defineEmits(['update:modelValue']);
const inputValue = ref('');

const handleInput = (event) => {
  inputValue.value = event.target.value;
};

const addItem = () => {
  if (inputValue.value.trim()) {
    const newValue = [...props.modelValue, inputValue.value.trim()];
    emit('update:modelValue', newValue);
    inputValue.value = '';
  }
};

const removeItem = (index) => {
  const newValue = [...props.modelValue];
  newValue.splice(index, 1);
  emit('update:modelValue', newValue);
};
</script>
