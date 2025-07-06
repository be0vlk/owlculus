<template>
  <v-dialog v-model="showDialog" max-width="500" persistent>
    <v-card>
      <v-card-title class="d-flex align-center pa-6">
        <v-icon :color="dialogIconColor" :icon="dialogIcon" class="me-3" size="large" />
        <span class="text-h5 font-weight-medium">{{ dialogTitle }}</span>
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-6">
        <div class="text-body-1 mb-4" v-html="dialogMessage" />
        <v-alert v-if="warningText" class="mb-0" type="warning" variant="tonal">
          <div class="text-body-2">
            <strong>{{ warningText }}</strong>
          </div>
        </v-alert>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-6">
        <v-spacer />
        <v-btn :disabled="loading" color="primary" variant="text" @click="handleCancel">
          {{ cancelButtonText }}
        </v-btn>
        <v-btn
          variant="flat"
          :color="confirmButtonColor"
          @click="handleConfirm"
          :loading="loading"
          prepend-icon="mdi-check"
        >
          {{ confirmButtonText }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { useConfirmationDialog } from '@/composables/useConfirmationDialog'

const {
  // State
  showDialog,
  dialogTitle,
  dialogMessage,
  dialogIcon,
  dialogIconColor,
  confirmButtonText,
  confirmButtonColor,
  cancelButtonText,
  loading,
  warningText,

  // Methods
  confirm,
  confirmDelete,
  confirmAction,
  handleConfirm,
  handleCancel,
} = useConfirmationDialog()

// Expose the confirm method for parent components
defineExpose({
  confirm,
  confirmDelete,
  confirmAction,
})
</script>
