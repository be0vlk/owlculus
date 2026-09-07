<template>
  <div>
    <v-tabs v-model="activeTab" color="on-surface" show-arrows aria-label="Case workspaces">
      <v-tab v-for="tab in tabs" :key="tab.name" :text="tab.label" :value="tab.name" />
    </v-tabs>

    <v-window v-model="activeTab" class="case-tab-window" :touch="false" :transition="false">
      <v-window-item
        v-for="tab in tabs"
        :key="tab.name"
        :value="tab.name"
        eager
        :transition="false"
      >
        <v-container fluid class="pa-0">
          <slot :active-tab="tab.name" />
        </v-container>
      </v-window-item>
    </v-window>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  tabs: {
    type: Array,
    required: true,
    default: () => [],
  },
  modelValue: {
    type: String,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue'])

const activeTab = computed({
  get: () => props.modelValue || props.tabs[0]?.name,
  set: (tabName) => emit('update:modelValue', tabName),
})
</script>

<style scoped>
:deep(.v-tab:focus-visible) {
  outline: 2px solid currentColor;
  outline-offset: -3px;
}

.case-tab-window {
  min-height: 200px;
}
</style>
