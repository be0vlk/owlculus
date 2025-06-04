<template>
  <v-chip
    variant="tonal"
    color="primary"
    size="small"
    class="ma-1"
    @click="$emit('click')"
  >
    <slot></slot>
  </v-chip>
</template>

<script setup>
defineEmits(['click']);
</script>
