<template>
  <v-card-actions class="pa-4">
    <v-spacer />

    <!-- Edit Mode Actions -->
    <template v-if="isEditing">
      <v-btn :disabled="updating" prepend-icon="mdi-close" variant="text" @click="$emit('cancel')">
        Cancel
      </v-btn>
      <v-btn
        color="primary"
        variant="flat"
        prepend-icon="mdi-content-save"
        @click="$emit('save')"
        :disabled="updating"
        :loading="updating"
      >
        {{ updating ? 'Saving...' : 'Save Changes' }}
      </v-btn>
    </template>

    <!-- View Mode Actions -->
    <template v-else>
      <v-btn prepend-icon="mdi-close" variant="text" @click="$emit('close')"> Close </v-btn>
      <v-btn color="primary" prepend-icon="mdi-pencil" variant="flat" @click="$emit('edit')">
        Edit Entity
      </v-btn>
    </template>
  </v-card-actions>
</template>

<script setup>
defineProps({
  isEditing: { type: Boolean, required: true },
  updating: { type: Boolean, required: true },
})

defineEmits(['close', 'edit', 'cancel', 'save'])
</script>
