<template>
  <v-chip class="ma-1" color="primary" size="small" variant="tonal" @click="$emit('click')">
    <slot></slot>
  </v-chip>
</template>

<script setup>
defineEmits(['click'])
</script>
