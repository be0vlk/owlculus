<template>
  <v-list-item class="py-4">
    <template v-slot:prepend>
      <div class="flex-grow-1">
        <v-list-item-title class="text-body-2 font-weight-medium text-truncate">
          <slot name="name" />
        </v-list-item-title>
        <v-list-item-subtitle
          v-if="hasDetail"
          class="text-body-2 text-truncate text-medium-emphasis"
        >
          <slot name="detail" />
        </v-list-item-subtitle>
      </div>
    </template>

    <template v-slot:append>
      <v-btn size="small" variant="outlined" @click="$emit('viewDetails')"> View Details </v-btn>
    </template>
  </v-list-item>
</template>

<script setup>
// Vuetify components are auto-imported

defineProps({
  hasDetail: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['viewDetails'])
</script>
