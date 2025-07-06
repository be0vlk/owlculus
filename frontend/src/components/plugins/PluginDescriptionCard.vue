<template>
  <v-card v-if="description" class="pa-3" color="blue-lighten-5" elevation="0" rounded="lg">
    <div class="d-flex align-center ga-2 mb-2">
      <v-icon color="blue">mdi-information</v-icon>
      <span class="text-subtitle2 font-weight-medium">About</span>
    </div>
    <p class="text-body-2 mb-0">
      {{ description }}
    </p>
  </v-card>
</template>

<script setup>
defineProps({
  description: {
    type: String,
    required: true,
  },
})
</script>
