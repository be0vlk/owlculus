<template>
    <div class="flex justify-center items-center" :class="sizeClass">
      <div class="animate-spin rounded-full border-b-2" :class="[colorClass, borderSizeClass]"></div>
    </div>
  </template>
  
  <script setup>
  import { computed } from 'vue';
  
  const props = defineProps({
    size: {
      type: String,
      default: 'medium',
    },
    color: {
      type: String,
      default: 'blue',
    },
  });
  
  const sizeClass = computed(() => {
    switch (props.size) {
      case 'small':
        return 'h-8 w-8';
      case 'large':
        return 'h-16 w-16';
      default:
        return 'h-12 w-12';
    }
  });
  
  const borderSizeClass = computed(() => {
      switch (props.size) {
          case 'small':
          return 'border-2';
          case 'large':
          return 'border-8';
          default:
          return 'border-4';
      }
  })
  
  const colorClass = computed(() => `border-${props.color}-500`);
  </script>