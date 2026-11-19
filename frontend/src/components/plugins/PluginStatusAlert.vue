<template>
  <v-alert
    v-if="message"
    :type="style.type"
    variant="tonal"
    :density="type === 'status' ? 'compact' : 'default'"
    :prominent="type === 'error'"
    :class="{ 'mb-4': type === 'complete' }"
  >
    <template v-if="style.title" #title>
      <div class="d-flex align-center">
        <v-icon :icon="style.icon" class="mr-2" />
        {{ pluginName ? `${pluginName} ${style.title}` : '' }}
      </div>
    </template>
    <div v-if="style.title">
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

const styles = {
  status: { type: 'info' },
  complete: { type: 'success', icon: 'mdi-check-circle', title: 'Complete' },
  error: { type: 'error', icon: 'mdi-alert-circle', title: 'Error' },
}
const style = computed(() => styles[props.type])
</script>
