<template>
  <v-dialog v-model="dialogVisible" max-width="600px" persistent>
    <v-card prepend-icon="mdi-account-plus" title="Add User to Case">
      <v-card-text>
        <!-- Loading State -->
        <v-row v-if="loading" justify="center">
          <v-col cols="12" class="text-center">
            <v-card variant="outlined" class="pa-8">
              <v-progress-circular class="mb-4" color="primary" indeterminate size="64" width="4" />
              <div class="text-h6">Loading Users...</div>
              <div class="text-body-2 text-medium-emphasis">
                Please wait while we fetch available users
              </div>
            </v-card>
          </v-col>
        </v-row>

        <!-- Error State -->
        <v-alert
          v-else-if="error"
          type="error"
          variant="tonal"
          border="start"
          icon="mdi-alert-circle"
          class="mb-6"
        >
          <v-alert-title>Error Loading Users</v-alert-title>
          {{ error }}
        </v-alert>

        <!-- User Selection Form -->
        <v-form v-else ref="formRef" v-model="isFormValid">
          <v-card variant="outlined" class="mb-6">
            <v-card-title class="text-subtitle-1 pb-2">
              <v-icon start>mdi-account-group</v-icon>
              User Selection
            </v-card-title>

            <v-card-text>
              <v-select
                v-model="selectedUserId"
                :items="enhancedUsers"
                item-title="displayText"
                item-value="id"
                label="Select User"
                variant="outlined"
                density="comfortable"
                placeholder="Choose a user to add to this case"
                :rules="[rules.required]"
                class="mb-4"
              />

              <v-checkbox
                v-model="isLead"
                color="primary"
                hint="Lead investigators have primary responsibility for the case"
                label="Set as Lead Investigator"
                persistent-hint
              />

              <v-alert
                v-if="availableUsers.length === 0"
                type="info"
                variant="tonal"
                icon="mdi-information"
              >
                <v-alert-title>No Users Available</v-alert-title>
                All users are already assigned to this case or no users exist in the system.
              </v-alert>
            </v-card-text>
          </v-card>
        </v-form>
      </v-card-text>

      <v-divider />

      <ModalActions
        submit-text="Add User"
        submit-icon="mdi-account-plus"
        :submit-disabled="!isFormValid || loading"
        :loading="loading"
        @cancel="$emit('close')"
        @submit="handleAddUser"
      />
    </v-card>
  </v-dialog>
</template>

<script setup>
import {computed, ref, watch} from 'vue'
import {userService} from '@/services/user'
import {caseService} from '@/services/case'
import ModalActions from './ModalActions.vue'

const props = defineProps({
  show: {
    type: Boolean,
    required: true,
  },
  caseId: {
    type: Number,
    required: true,
  },
})

const emit = defineEmits(['close', 'userAdded'])

// Reactive variables
const formRef = ref(null)
const isFormValid = ref(false)
const loading = ref(false)
const error = ref(null)
const selectedUserId = ref('')
const availableUsers = ref([])
const isLead = ref(false)

// Validation rules
const rules = {
  required: (value) => !!value || 'Please select a user',
}

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  },
})

// Enhanced computed property for user display
const enhancedUsers = computed(() => {
  return availableUsers.value.map((user) => ({
    ...user,
    displayText: `${user.email} - ${user.username}`,
  }))
})

const loadUsers = async () => {
  try {
    loading.value = true
    error.value = null
    availableUsers.value = await userService.getUsers()
  } catch (err) {
    error.value = err.response?.data?.message || err.message || 'Failed to load users'
  } finally {
    loading.value = false
  }
}

const handleAddUser = async () => {
  // Validate form before submission
  if (!formRef.value) return

  const { valid } = await formRef.value.validate()
  if (!valid) return

  try {
    loading.value = true
    error.value = null
    await caseService.addUserToCase(props.caseId, selectedUserId.value, isLead.value)
    emit('userAdded')
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.message || err.message || 'Failed to add user to case'
  } finally {
    loading.value = false
  }
}

// Watch for dialog opening/closing
watch(
  () => props.show,
  (newValue) => {
    if (newValue) {
      loadUsers()
      // Reset form validation when dialog opens
      setTimeout(() => {
        if (formRef.value) {
          formRef.value.resetValidation()
        }
      }, 100)
    } else {
      // Clear selection and errors when modal is closed
      selectedUserId.value = ''
      error.value = null
      isLead.value = false
    }
  },
)
</script>
