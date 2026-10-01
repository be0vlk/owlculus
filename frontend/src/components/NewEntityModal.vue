<template>
  <v-dialog
    v-model="dialogVisible"
    aria-label="Add New Entity"
    max-width="700px"
    :persistent="entityForm.state.loading"
  >
    <v-card prepend-icon="mdi-account-plus">
      <v-card-title id="new-entity-dialog-title">Add New Entity</v-card-title>
      <v-card-text>
        <EntityDuplicateAdvisory
          :candidates="entityForm.advisories.candidates.value"
          :case-id="caseId"
          :entity-type="entityForm.state.entityType"
          :loading="entityForm.state.loading"
          @continue="handleSubmit(true)"
        />
        <p v-if="!formValid" class="mb-4">
          {{ entityIdentityGuidance[entityForm.state.entityType] }}
        </p>
        <!-- Error Alert -->
        <v-alert v-if="entityForm.state.error" type="error" variant="tonal" class="mb-4">
          {{ entityForm.state.error }}
        </v-alert>

        <v-form @submit.prevent="handleSubmit">
          <!-- Entity Type Selector -->
          <v-card variant="outlined" class="mb-6">
            <v-card-title class="text-body-large pb-2">
              <v-icon start>mdi-shape</v-icon>
              Entity Type
            </v-card-title>

            <v-card-text class="pt-0">
              <v-tabs v-model="entityForm.state.entityType" color="primary" align-tabs="start">
                <v-tab
                  v-for="entityType in ENTITY_TYPES"
                  :key="entityType.value"
                  :value="entityType.value"
                  :prepend-icon="entityType.icon"
                >
                  {{ entityType.title }}
                </v-tab>
              </v-tabs>
            </v-card-text>
          </v-card>

          <!-- Entity Form Content -->
          <v-tabs-window v-model="entityForm.state.entityType">
            <v-tabs-window-item value="person">
              <PersonForm v-model="entityForm.state.data" />
            </v-tabs-window-item>

            <v-tabs-window-item value="company">
              <CompanyForm v-model="entityForm.state.data" />
            </v-tabs-window-item>

            <v-tabs-window-item value="domain">
              <DomainForm v-model="entityForm.state.data" />
            </v-tabs-window-item>

            <v-tabs-window-item value="ip_address">
              <IpAddressForm v-model="entityForm.state.data" />
            </v-tabs-window-item>

            <v-tabs-window-item value="vehicle">
              <VehicleForm v-model="entityForm.state.data" />
            </v-tabs-window-item>
          </v-tabs-window>

          <button aria-hidden="true" class="d-none" tabindex="-1" type="submit">
            Submit entity
          </button>
        </v-form>
      </v-card-text>

      <v-divider />

      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="entityForm.state.loading" variant="text" @click="cancelDialog">
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          @click="handleSubmit"
          :disabled="entityForm.state.loading || !formValid"
          :loading="entityForm.state.loading"
        >
          Add Entity
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import EntityDuplicateAdvisory from './entities/EntityDuplicateAdvisory.vue'
import { watch, computed } from 'vue'
import { useEntityForm } from '../composables/useEntityForm'
import { isFormValid, entityIdentityGuidance } from '../composables/entityValidation'
import { ENTITY_TYPES } from '../composables/entityTypes'
import { useDialogFocusRestore } from '../composables/useDialogFocusRestore'
import PersonForm from './entities/PersonForm.vue'
import CompanyForm from './entities/CompanyForm.vue'
import DomainForm from './entities/DomainForm.vue'
import IpAddressForm from './entities/IpAddressForm.vue'
import VehicleForm from './entities/VehicleForm.vue'

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  caseId: { type: String, required: true },
})

useDialogFocusRestore(() => props.show)

const emit = defineEmits(['close', 'created'])

const entityForm = useEntityForm(props.caseId)

// Dialog visibility
const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  },
})

const formValid = computed(() => isFormValid(entityForm.state.entityType, entityForm.state.data))

function cancelDialog() {
  if (!entityForm.state.loading) emit('close')
}

async function handleSubmit(confirmed = false) {
  if (!formValid.value || entityForm.state.loading) return

  try {
    const response = await entityForm.submitEntity(confirmed === true)
    if (!response) return
    emit('created', response)
    emit('close')
  } catch {
    // Error is already handled in the composable
  }
}

watch(
  () => props.show,
  (show) => {
    if (show) entityForm.reset()
  },
)
</script>
