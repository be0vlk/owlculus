<template>
  <v-card-actions class="pa-4">
    <v-spacer />
    <v-btn
      variant="text"
      prepend-icon="mdi-close"
      @click="$emit('cancel')"
      :disabled="loading"
    >
      {{ cancelText }}
    </v-btn>
    <v-btn
      v-if="showSubmit"
      :color="submitColor"
      variant="flat"
      :prepend-icon="submitIcon"
      @click="$emit('submit')"
      :disabled="submitDisabled"
      :loading="loading"
    >
      {{ loading && loadingText ? loadingText : submitText }}
    </v-btn>
  </v-card-actions>
</template>

<script setup>
defineProps({
  cancelText: {
    type: String,
    default: 'Cancel'
  },
  submitText: {
    type: String,
    required: true
  },
  submitIcon: {
    type: String,
    required: true
  },
  submitColor: {
    type: String,
    default: 'primary'
  },
  submitDisabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  },
  showSubmit: {
    type: Boolean,
    default: true
  },
  loadingText: {
    type: String,
    default: null
  }
})

defineEmits(['cancel', 'submit'])
</script>