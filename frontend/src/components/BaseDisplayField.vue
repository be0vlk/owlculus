<template>
    <div>
      <label class="block text-sm font-medium text-gray-500 dark:text-gray-400 underline">{{ label }}</label>
      <p class="mt-1 text-sm text-gray-900 dark:text-white">
        <slot>
          <template v-if="type === 'url' && value">
            <a :href="value" target="_blank" rel="noopener noreferrer" class="text-cyan-600 hover:text-cyan-500 dark:text-cyan-400 dark:hover:text-cyan-300">
              {{ value }}
            </a>
          </template>
          <template v-else>{{ value || '' }}</template>
        </slot>
      </p>
    </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number, Object], default: null },
  type: { type: String, default: 'text' },
});
</script>