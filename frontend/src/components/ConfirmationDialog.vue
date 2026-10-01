<template>
  <v-dialog
    v-model="showDialog"
    :aria-label="opts.title"
    max-width="500"
    persistent
    @keydown.esc="handleCancel"
  >
    <v-card>
      <v-card-title class="d-flex align-center pa-6">
        <v-icon :color="opts.iconColor" :icon="opts.icon" class="me-3" size="large" />
        <span class="text-headline-small font-weight-medium">{{ opts.title }}</span>
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-6">
        <p class="text-body-large mb-4">{{ opts.message }}</p>
        <v-alert v-if="opts.warning" class="mb-0" type="warning" variant="tonal">
          <div class="text-body-medium">
            <strong>{{ opts.warning }}</strong>
          </div>
        </v-alert>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-6">
        <v-spacer />
        <v-btn color="primary" variant="text" @click="handleCancel">
          {{ opts.cancelText }}
        </v-btn>
        <v-btn
          variant="flat"
          :color="opts.confirmColor"
          @click="handleConfirm"
          prepend-icon="mdi-check"
        >
          {{ opts.confirmText }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { useConfirmationDialog } from '@/composables/useConfirmationDialog'

const { showDialog, opts, confirm, confirmDelete, handleConfirm, handleCancel } =
  useConfirmationDialog()

defineExpose({ confirm, confirmDelete })
</script>
