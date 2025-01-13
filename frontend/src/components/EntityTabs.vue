<template>
  <div>
    <div class="border-b border-gray-200 dark:border-gray-700">
      <nav class="-mb-px flex space-x-8" aria-label="Tabs">
        <button
          v-for="type in entityTypes"
          :key="type"
          @click="activeType = type"
          :class="[
            activeType === type
              ? 'border-cyan-500 text-cyan-600 dark:text-cyan-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300',
            'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm'
          ]"
        >
          {{ getDisplayName(type) }}
        </button>
      </nav>
    </div>

    <div class="mt-4">
      <slot :active-type="activeType" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

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

const activeType = ref(props.entityTypes[0] || '')

const getDisplayName = (type) => {
  return entityDisplayNames[type] || type;
}
</script>