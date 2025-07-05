<template>
  <v-alert
    v-if="message"
    :type="alertType"
    :variant="variant"
    :density="density"
    :prominent="prominent"
    :class="alertClass"
  >
    <template v-if="showTitle" #title>
      <div class="d-flex align-center">
        <v-icon :icon="titleIcon" class="mr-2" />
        {{ titleText }}
      </div>
    </template>
    <div v-if="showTitle">
      {{ message }}
    </div>
    <template v-else>
      {{ message }}
    </template>
  </v-alert>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (value) => ['status', 'complete', 'error'].includes(value),
  },
  message: {
    type: String,
    required: true,
  },
  pluginName: {
    type: String,
    default: '',
  },
})

const alertType = computed(() => {
  switch (props.type) {
    case 'status':
      return 'info'
    case 'complete':
      return 'success'
    case 'error':
      return 'error'
    default:
      return 'info'
  }
})

const variant = computed(() => (props.type === 'status' ? 'tonal' : 'tonal'))
const density = computed(() => (props.type === 'status' ? 'compact' : 'default'))
const prominent = computed(() => props.type === 'error')
const alertClass = computed(() => (props.type === 'complete' ? 'mb-4' : ''))

const showTitle = computed(() => props.type !== 'status')

const titleIcon = computed(() => {
  switch (props.type) {
    case 'complete':
      return 'mdi-check-circle'
    case 'error':
      return 'mdi-alert-circle'
    default:
      return ''
  }
})

const titleText = computed(() => {
  if (props.pluginName) {
    switch (props.type) {
      case 'complete':
        return `${props.pluginName} Complete`
      case 'error':
        return `${props.pluginName} Error`
      default:
        return ''
    }
  }
  return ''
})
</script>
