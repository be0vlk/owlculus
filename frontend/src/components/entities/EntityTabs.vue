<template>
  <v-tabs v-model="activeType">
    <v-tab v-for="type in entityTypes" :key="type" :value="type">
      {{ getDisplayName(type) }}
    </v-tab>
  </v-tabs>
  <v-window v-model="activeType">
    <v-window-item v-for="type in entityTypes" :key="type" :value="type">
      <div class="pt-4">
        <slot :active-type="type" />
      </div>
    </v-window-item>
  </v-window>
</template>

<script setup>
import { ref } from 'vue'
// Vuetify components are auto-imported

const entityDisplayNames = {
  person: 'Person',
  company: 'Company',
  domain: 'Domain',
  ip_address: 'IP Address'
};

const props = defineProps({
  entityTypes: {
    type: Array,
    required: true
  }
})

const activeType = ref(props.entityTypes[0] || '');

const getDisplayName = (type) => {
  return entityDisplayNames[type] || type;
}
</script>