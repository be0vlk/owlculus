<template>
  <div>
    <v-tabs v-model="activeTab" color="primary">
      <v-tab v-for="tab in tabs" :key="tab.name" :text="tab.label" :value="tab.name" />
    </v-tabs>

    <v-window v-model="activeTab" :touch="false" :transition="false">
      <v-window-item v-for="tab in tabs" :key="tab.name" :value="tab.name" eager :transition="false">
        <v-container class="pa-4">
          <slot :active-tab="tab.name" />
        </v-container>
      </v-window-item>
    </v-window>
  </div>
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

<style scoped>
/* Workaround for Vuetify 3 scroll-to-top bug */
.v-window {
  min-height: 200px; /* Prevents height collapse during transitions */
}
</style>
