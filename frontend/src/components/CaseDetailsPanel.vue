<template>
  <v-dialog
    v-model="open"
    aria-label="Case details"
    class="case-details-panel"
    :transition="false"
    :retain-focus="!nestedDialogOpen"
    :persistent="nestedDialogOpen"
    :no-click-animation="true"
    scrollable
  >
    <v-card>
      <v-card-title class="d-flex flex-wrap align-center ga-2 pa-4">
        <h2 class="text-title-large">Case details</h2>
        <v-spacer />
        <v-btn variant="text" prepend-icon="mdi-close" @click="open = false">
          Close Case details
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-5">
        <v-alert v-if="refreshError" type="error" variant="tonal" class="mb-4">
          {{ refreshError }}
          <v-btn variant="text" @click="$emit('retry')">Retry case details</v-btn>
        </v-alert>
        <p class="text-label-large mb-4 case-number">{{ caseData.case_number }}</p>
        <CaseDetail :case-data="caseData" :client="client" />
        <div class="d-flex flex-wrap ga-2 mt-4">
          <v-btn v-if="canEdit" variant="outlined" prepend-icon="mdi-pencil" @click="$emit('edit')">
            Edit Case
          </v-btn>
          <v-btn
            v-if="canManageUsers"
            variant="outlined"
            prepend-icon="mdi-account-group"
            @click="$emit('manage-users')"
          >
            Manage Users
          </v-btn>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'
import CaseDetail from './CaseDetail.vue'
import { useDialogFocusRestore } from '../composables/useDialogFocusRestore'

const props = defineProps({
  modelValue: Boolean,
  caseData: { type: Object, required: true },
  client: { type: Object, default: null },
  refreshError: { type: String, default: '' },
  canEdit: Boolean,
  canManageUsers: Boolean,
  nestedDialogOpen: Boolean,
})
const emit = defineEmits(['update:modelValue', 'edit', 'manage-users', 'retry'])
const open = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})
useDialogFocusRestore(open)
</script>

<style scoped>
.case-details-panel :deep(.v-overlay__content) {
  inset-inline-end: 0;
  margin: 0;
  width: min(520px, 100%);
  max-width: 100%;
  height: 100%;
  max-height: 100%;
}

.case-details-panel :deep(.v-card) {
  border-radius: 0;
}

.case-number {
  overflow-wrap: anywhere;
}
</style>
