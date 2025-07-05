<template>
  <v-dialog v-model="dialogVisible" max-width="800px" persistent>
    <v-card prepend-icon="mdi-account-group" title="Manage Case Users">
      <v-card-text>
        <!-- Loading State -->
        <v-row v-if="loading" justify="center">
          <v-col class="text-center" cols="12">
            <v-card class="pa-8" variant="outlined">
              <v-progress-circular class="mb-4" color="primary" indeterminate size="64" width="4" />
              <div class="text-h6">Loading Users...</div>
              <div class="text-body-2 text-medium-emphasis">
                Please wait while we fetch user data
              </div>
            </v-card>
          </v-col>
        </v-row>

        <!-- Error State -->
        <v-alert
          v-else-if="error"
          border="start"
          class="mb-6"
          icon="mdi-alert-circle"
          type="error"
          variant="tonal"
        >
          <v-alert-title>Error Loading Users</v-alert-title>
          {{ error }}
        </v-alert>

        <div v-else>
          <!-- Current Users Section -->
          <v-card class="mb-6" variant="outlined">
            <v-card-title class="text-subtitle-1 pb-2">
              <v-icon start>mdi-account-check</v-icon>
              Current Case Users
            </v-card-title>

            <v-card-text>
              <v-list v-if="caseUsers.length > 0" density="compact">
                <v-list-item
                  v-for="user in caseUsers"
                  :key="user.id"
                  class="px-0"
                >
                  <template #prepend>
                    <v-avatar color="grey-lighten-1" size="32">
                      <v-icon>mdi-account</v-icon>
                    </v-avatar>
                  </template>

                  <v-list-item-title>
                    {{ user.email }}
                    <v-chip
                      v-if="user.is_lead"
                      class="ml-2"
                      color="primary"
                      size="x-small"
                      variant="tonal"
                    >
                      Lead
                    </v-chip>
                  </v-list-item-title>
                  <v-list-item-subtitle>{{ user.username }}</v-list-item-subtitle>

                  <template #append>
                    <div class="d-flex align-center ga-1">
                      <v-tooltip
                        :text="user.is_lead ? 'Remove as Lead' : 'Set as Lead'"
                        location="top"
                      >
                        <template #activator="{ props }">
                          <v-btn
                            :color="user.is_lead ? 'primary' : 'default'"
                            :icon="user.is_lead ? 'mdi-star' : 'mdi-star-outline'"
                            :loading="updatingLeadStatus === user.id"
                            size="small"
                            v-bind="props"
                            variant="text"
                            @click="toggleLeadStatus(user)"
                          />
                        </template>
                      </v-tooltip>

                      <v-tooltip location="top" text="Remove from Case">
                        <template #activator="{ props }">
                          <v-btn
                            :loading="removingUser === user.id"
                            color="error"
                            icon="mdi-account-remove"
                            size="small"
                            v-bind="props"
                            variant="text"
                            @click="removeUser(user)"
                          />
                        </template>
                      </v-tooltip>
                    </div>
                  </template>
                </v-list-item>
              </v-list>

              <v-alert
                v-else
                icon="mdi-information"
                type="info"
                variant="tonal"
              >
                No users are currently assigned to this case
              </v-alert>
            </v-card-text>
          </v-card>

          <!-- Add New User Section -->
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-1 pb-2">
              <v-icon start>mdi-account-plus</v-icon>
              Add New User
            </v-card-title>

            <v-card-text>
              <v-form ref="formRef" v-model="isFormValid">
                <v-row align="center">
                  <v-col cols="12" md="6">
                    <v-select
                      v-model="selectedUserId"
                      :items="availableUsers"
                      :rules="[rules.required]"
                      clearable
                      density="comfortable"
                      item-title="displayText"
                      item-value="id"
                      label="Select User"
                      placeholder="Choose a user to add"
                      variant="outlined"
                    />
                  </v-col>
                  <v-col cols="12" md="3">
                    <v-checkbox
                      v-model="isLead"
                      density="comfortable"
                      hide-details
                      label="Set as Lead"
                    />
                  </v-col>
                  <v-col cols="12" md="3">
                    <v-btn
                      :disabled="!selectedUserId"
                      :loading="addingUser"
                      block
                      color="primary"
                      prepend-icon="mdi-account-plus"
                      variant="tonal"
                      @click="addUser"
                    >
                      Add User
                    </v-btn>
                  </v-col>
                </v-row>
              </v-form>

              <v-alert
                v-if="availableUsers.length === 0"
                class="mt-4"
                icon="mdi-information"
                type="info"
                variant="tonal"
              >
                <v-alert-title>No Users Available</v-alert-title>
                All users are already assigned to this case
              </v-alert>
            </v-card-text>
          </v-card>
        </div>
      </v-card-text>

      <v-divider />

      <ModalActions
        :loading="loading"
        :show-cancel="false"
        submit-icon="mdi-check"
        submit-text="Done"
        @submit="$emit('close')"
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
  caseData: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['close', 'updated'])

// Reactive variables
const formRef = ref(null)
const isFormValid = ref(false)
const loading = ref(false)
const error = ref(null)
const selectedUserId = ref(null)
const isLead = ref(false)
const allUsers = ref([])
const addingUser = ref(false)
const removingUser = ref(null)
const updatingLeadStatus = ref(null)

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

// Current case users
const caseUsers = computed(() => props.caseData?.users || [])

// Available users (not already in case)
const availableUsers = computed(() => {
  const caseUserIds = caseUsers.value.map(u => u.id)
  return allUsers.value
    .filter(user => !caseUserIds.includes(user.id))
    .map(user => ({
      ...user,
      displayText: `${user.email} - ${user.username}`,
    }))
})

const loadUsers = async () => {
  try {
    loading.value = true
    error.value = null
    allUsers.value = await userService.getUsers()
  } catch (err) {
    error.value = err.response?.data?.message || err.message || 'Failed to load users'
  } finally {
    loading.value = false
  }
}

const addUser = async () => {
  if (!selectedUserId.value) return

  try {
    addingUser.value = true
    error.value = null
    await caseService.addUserToCase(props.caseId, selectedUserId.value, isLead.value)
    emit('updated')

    // Reset form
    selectedUserId.value = null
    isLead.value = false
    if (formRef.value) {
      formRef.value.resetValidation()
    }
  } catch (err) {
    error.value = err.response?.data?.message || err.message || 'Failed to add user to case'
  } finally {
    addingUser.value = false
  }
}

const removeUser = async (user) => {
  if (!confirm(`Are you sure you want to remove ${user.email} from this case?`)) {
    return
  }

  try {
    removingUser.value = user.id
    error.value = null
    await caseService.removeUserFromCase(props.caseId, user.id)
    emit('updated')
  } catch (err) {
    error.value = err.response?.data?.message || err.message || 'Failed to remove user from case'
  } finally {
    removingUser.value = null
  }
}

const toggleLeadStatus = async (user) => {
  try {
    updatingLeadStatus.value = user.id
    error.value = null
    await caseService.updateCaseUserLeadStatus(props.caseId, user.id, !user.is_lead)
    emit('updated')
  } catch (err) {
    error.value = err.response?.data?.message || err.message || 'Failed to update lead status'
  } finally {
    updatingLeadStatus.value = null
  }
}

// Watch for dialog opening/closing
watch(
  () => props.show,
  (newValue) => {
    if (newValue) {
      loadUsers()
      // Reset form when dialog opens
      selectedUserId.value = null
      isLead.value = false
      error.value = null
      if (formRef.value) {
        setTimeout(() => {
          formRef.value.resetValidation()
        }, 100)
      }
    }
  },
)
</script>
