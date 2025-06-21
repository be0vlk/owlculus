<template>
  <v-dialog v-model="dialogVisible" max-width="700px" persistent>
    <v-card prepend-icon="mdi-account-plus" title="Add New Entity">
      <v-card-text>
        <!-- Error Alert -->
        <v-alert v-if="entityForm.state.error" type="error" variant="tonal" class="mb-4">
          {{ entityForm.state.error }}
        </v-alert>

        <v-form ref="formRef" @submit.prevent="handleSubmit">
          <!-- Entity Type Selector -->
          <v-card variant="outlined" class="mb-6">
            <v-card-title class="text-subtitle-1 pb-2">
              <v-icon start>mdi-shape</v-icon>
              Entity Type
            </v-card-title>

            <v-card-text class="pt-0">
              <v-tabs
                v-model="selectedTab"
                color="primary"
                align-tabs="start"
                @update:model-value="handleTabChange"
              >
                <v-tab
                  v-for="entityType in entityTypes"
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
          <v-tabs-window v-model="selectedTab">
            <v-tabs-window-item value="person">
              <PersonForm
                v-model="entityForm.state.data"
                @update:model-value="entityForm.updateData"
              />
            </v-tabs-window-item>

            <v-tabs-window-item value="company">
              <CompanyForm
                v-model="entityForm.state.data"
                @update:model-value="entityForm.updateData"
              />
            </v-tabs-window-item>

            <v-tabs-window-item value="domain">
              <DomainForm
                v-model="entityForm.state.data"
                @update:model-value="entityForm.updateData"
              />
            </v-tabs-window-item>

            <v-tabs-window-item value="ip_address">
              <IpAddressForm
                v-model="entityForm.state.data"
                @update:model-value="entityForm.updateData"
              />
            </v-tabs-window-item>

            <v-tabs-window-item value="vehicle">
              <VehicleForm
                v-model="entityForm.state.data"
                @update:model-value="entityForm.updateData"
              />
            </v-tabs-window-item>
          </v-tabs-window>
        </v-form>
      </v-card-text>

      <v-divider />

      <v-card-actions>
        <v-spacer />
        <v-btn
          variant="text"
          @click="$emit('close')"
          :disabled="entityForm.state.loading"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
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
import { watch, computed, ref } from 'vue'
import { useEntityForm } from '../composables/useEntityForm'
import { useEntityValidation } from '../composables/useEntityValidation'
import PersonForm from './entities/PersonForm.vue'
import CompanyForm from './entities/CompanyForm.vue'
import DomainForm from './entities/DomainForm.vue'
import IpAddressForm from './entities/IpAddressForm.vue'
import VehicleForm from './entities/VehicleForm.vue'

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  caseId: { type: String, required: true },
})

const emit = defineEmits(['close', 'created'])

// Entity types configuration
const entityTypes = [
  { value: 'person', title: 'Person', icon: 'mdi-account' },
  { value: 'company', title: 'Company', icon: 'mdi-domain' },
  { value: 'domain', title: 'Domain', icon: 'mdi-web' },
  { value: 'ip_address', title: 'IP Address', icon: 'mdi-ip' },
  { value: 'vehicle', title: 'Vehicle', icon: 'mdi-car' }
]

// Reactive variables
const selectedTab = ref('person')
const formRef = ref(null)

// Composables
const entityForm = useEntityForm(props.caseId)
const { isFormValid } = useEntityValidation()

// Dialog visibility
const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
})

// Computed validation
const formValid = computed(() => 
  isFormValid(entityForm.state.entityType, entityForm.state.data)
)

// Handle tab change
function handleTabChange(newTab) {
  entityForm.setEntityType(newTab)
}

// Handle form submission
async function handleSubmit() {
  try {
    const response = await entityForm.submitEntity()
    emit('created', response)
    emit('close')
  } catch {
    // Error is already handled in the composable
  }
}

// Watch for tab changes to sync with entity type
watch(selectedTab, (newTab) => {
  if (newTab !== entityForm.state.entityType) {
    entityForm.setEntityType(newTab)
  }
})

// Watch for entity type changes to sync with tabs
watch(() => entityForm.state.entityType, (newType) => {
  selectedTab.value = newType
})

// Initialize form when dialog opens
watch(() => props.show, (show) => {
  if (show) {
    entityForm.reset()
    selectedTab.value = 'person'
  }
})
</script>
