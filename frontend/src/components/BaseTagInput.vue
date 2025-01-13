<template>
  <div>
    <label :for="id" class="block text-sm font-medium text-gray-700 dark:text-gray-300">{{ label }}</label>
    <div class="mt-1">
      <!-- Tags display -->
      <div class="flex flex-wrap gap-2 mb-2">
        <span
          v-for="(tag, index) in modelValue"
          :key="index"
          class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-cyan-100 text-cyan-800 dark:bg-cyan-800 dark:text-cyan-100"
        >
          {{ tag }}
          <button
            type="button"
            @click="removeTag(index)"
            class="ml-1 inline-flex items-center p-0.5 hover:bg-cyan-200 dark:hover:bg-cyan-700 rounded-full"
          >
            <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </span>
      </div>
      
      <!-- Input field -->
      <div class="flex">
        <input
          :id="id"
          type="text"
          v-model="inputValue"
          @keydown.enter.prevent="addTag"
          @keydown.backspace="handleBackspace"
          class="shadow-sm focus:ring-cyan-500 focus:border-cyan-500 block w-full sm:text-sm border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          :placeholder="placeholder || 'Type and press Enter to add'"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  modelValue: {
    type: Array,
    required: true,
    default: () => []
  },
  label: {
    type: String,
    required: true
  },
  id: {
    type: String,
    required: true
  },
  placeholder: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue']);
const inputValue = ref('');

const addTag = () => {
  const value = inputValue.value.trim();
  if (value && !props.modelValue.includes(value)) {
    emit('update:modelValue', [...props.modelValue, value]);
    inputValue.value = '';
  }
};

const removeTag = (index) => {
  const newTags = [...props.modelValue];
  newTags.splice(index, 1);
  emit('update:modelValue', newTags);
};

const handleBackspace = (event) => {
  if (inputValue.value === '' && props.modelValue.length > 0) {
    event.preventDefault();
    removeTag(props.modelValue.length - 1);
  }
};
</script>
