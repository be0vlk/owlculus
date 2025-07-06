<template>
  <v-tabs v-model="activeTab" color="primary">
    <v-tab v-for="tab in tabs" :key="tab.name" :text="tab.label" :value="tab.name" />
  </v-tabs>

  <v-tabs-window v-model="activeTab">
    <v-tabs-window-item v-for="tab in tabs" :key="tab.name" :value="tab.name">
      <v-container class="pa-4">
        <slot :active-tab="tab.name" />
      </v-container>
    </v-tabs-window-item>
  </v-tabs-window>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  tabs: {
    type: Array,
    required: true,
    default: () => [],
  },
})

const activeTab = ref(props.tabs[0]?.name)
</script>
