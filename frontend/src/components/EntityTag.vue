<template>
  <button 
    @click="$emit('click')"
    class="inline-flex items-center px-2.5 py-1.5 m-0.5 rounded-full text-xs font-medium bg-cyan-100 text-cyan-800 hover:bg-cyan-200 dark:bg-cyan-900 dark:text-cyan-100 dark:hover:bg-cyan-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500"
  >
    <slot></slot>
  </button>
</template>

<script setup>
defineEmits(['click']);
</script>
