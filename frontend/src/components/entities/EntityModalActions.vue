<template>
  <v-card-actions class="pa-4">
    <v-spacer />

    <!-- Edit Mode Actions -->
    <template v-if="isEditing">
      <v-btn
        variant="text"
        prepend-icon="mdi-close"
        @click="$emit('cancel')"
        :disabled="updating"
      >
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
      <v-btn
        variant="text"
        prepend-icon="mdi-close"
        @click="$emit('close')"
      >
        Close
      </v-btn>
      <v-btn
        color="primary"
        variant="flat"
        prepend-icon="mdi-pencil"
        @click="$emit('edit')"
      >
        Edit Entity
      </v-btn>
    </template>
  </v-card-actions>
</template>

<script setup>
defineProps({
  isEditing: { type: Boolean, required: true },
  updating: { type: Boolean, required: true }
})

defineEmits(['close', 'edit', 'cancel', 'save'])
</script>