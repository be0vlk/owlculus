<template>
  <div class="plugin-result">
    <component 
      v-if="pluginComponent"
      :is="pluginComponent"
      :result="result"
    />
    <div v-else class="fallback-result">
      <!-- Fallback for plugins without custom components -->
      <template v-if="Array.isArray(result)">
        <div v-for="(item, index) in result" :key="index" class="bg-white dark:bg-gray-800 shadow-sm rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <pre class="text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono text-sm">{{ formatValue(item) }}</pre>
        </div>
      </template>
      <template v-else-if="typeof result === 'object' && result !== null">
        <div v-for="(value, key) in result" :key="key" class="bg-white dark:bg-gray-800 shadow-sm rounded-lg p-4 mb-2 last:mb-0 border border-gray-200 dark:border-gray-700">
          <div class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
            {{ formatKey(key) }}
          </div>
          <div class="text-gray-700 dark:text-gray-300">
            <pre class="whitespace-pre-wrap font-mono text-sm">{{ formatValue(value) }}</pre>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="bg-white dark:bg-gray-800 shadow-sm rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <pre class="text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono text-sm">{{ formatValue(result) }}</pre>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { defineProps, shallowRef, watch } from 'vue';

const props = defineProps({
  result: {
    type: [Object, Array, String, Number, Boolean, null],
    required: true,
  },
  pluginName: {
    type: String,
    required: true
  }
});

// Use shallowRef for better performance with async components
const pluginComponent = shallowRef(null);

const loadPluginComponent = async () => {
  // Get plugin name and ensure proper casing
  const name = props.pluginName
    .replace(/Plugin$/, '') // Remove 'Plugin' suffix if present
    .replace(/^[a-z]/, c => c.toUpperCase()); // Ensure first letter is uppercase
  
  const componentName = `${name}PluginResult`;
  
  try {
    // Update import path to use absolute path from src
    const module = await import(`@/components/plugins/${componentName}.vue`);
    pluginComponent.value = module.default;
  } catch (error) {
    console.log(`No custom component found for plugin: ${componentName}`, error);
    pluginComponent.value = null;
  }
};

// Watch both plugin name and result changes
watch([() => props.pluginName, () => props.result], () => {
  loadPluginComponent();
}, { immediate: true });

const formatKey = (key) => {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

const formatValue = (value) => {
  if (value === null) return 'Not available';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};
</script>

<style scoped>
.plugin-result {
  width: 100%;
}

.fallback-result {
  width: 100%;
}
</style>