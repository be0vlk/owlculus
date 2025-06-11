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
        <v-card v-for="(item, index) in result" :key="index" elevation="1" rounded="lg" class="mb-2">
          <v-card-text>
            <pre class="text-body-2 font-mono">{{ formatValue(item) }}</pre>
          </v-card-text>
        </v-card>
      </template>
      <template v-else-if="typeof result === 'object' && result !== null">
        <v-card v-for="(value, key) in result" :key="key" elevation="1" rounded="lg" class="mb-2">
          <v-card-text>
            <div class="text-body-2 font-weight-medium text-medium-emphasis mb-1">
              {{ formatKey(key) }}
            </div>
            <pre class="text-body-2 font-mono">{{ formatValue(value) }}</pre>
          </v-card-text>
        </v-card>
      </template>
      <template v-else>
        <v-card elevation="1" rounded="lg">
          <v-card-text>
            <pre class="text-body-2 font-mono">{{ formatValue(result) }}</pre>
          </v-card-text>
        </v-card>
      </template>
    </div>
  </div>
</template>

<script setup>
import { defineProps, shallowRef, watch, markRaw } from 'vue';

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
    // Use relative path for dynamic imports
    const module = await import(`./${componentName}.vue`);
    pluginComponent.value = markRaw(module.default);
  } catch (error) {
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