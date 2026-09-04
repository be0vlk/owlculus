<template>
  <div>
    <v-tabs v-model="activeTab" color="primary">
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
        <v-container class="pa-4">
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
  get: () =>
    props.tabs.some((tab) => tab.name === props.modelValue)
      ? props.modelValue
      : props.tabs[0]?.name,
  set: (tabName) => emit('update:modelValue', tabName),
})
</script>

<style scoped>
.case-tab-window {
  min-height: 200px;
}
</style>
