<template>
  <v-dialog
    v-model="dialogVisible"
    aria-label="Manage Case Users"
    max-width="800px"
    persistent
    @keydown.esc="!loading && $emit('close')"
  >
    <v-card prepend-icon="mdi-account-group">
      <v-card-title id="manage-case-users-dialog-title">Manage Case Users</v-card-title>
      <v-card-text>
        <!-- Loading State -->
        <v-row class="justify-center" v-if="loading">
          <v-col class="text-center" cols="12">
            <v-card class="pa-8" variant="outlined">
              <v-progress-circular class="mb-4" color="primary" indeterminate size="64" width="4" />
              <div class="text-title-large">Loading Users...</div>
              <div class="text-body-medium text-medium-emphasis">
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

        <v-card v-else variant="outlined">
          <v-card-title class="text-body-large pb-2">
            <v-icon start>mdi-account-check</v-icon>
            Case Users
          </v-card-title>
          <v-card-text>
            <CaseUserList
              :users="caseUsers"
              :all-users="allUsers"
              :adding="addingUser"
              :busy-user-id="busyUserId"
              autofocus
              remove-target="case"
              @add="addUser"
              @toggle-lead="toggleLeadStatus"
              @remove="removeUser"
            >
              <template #empty>
                <v-alert class="mb-4" icon="mdi-information" type="info" variant="tonal">
                  No users are currently assigned to this case
                </v-alert>
              </template>
            </CaseUserList>
          </v-card-text>
        </v-card>
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
import { computed, ref, watch } from 'vue'
import { userService } from '@/services/user'
import { caseService } from '@/services/case'
import { useDialogFocusRestore } from '@/composables/useDialogFocusRestore'
import { getErrorMessage } from '@/utils/errorMessage'
import ModalActions from './ModalActions.vue'
import CaseUserList from './CaseUserList.vue'

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

useDialogFocusRestore(() => props.show)

const emit = defineEmits(['close', 'updated'])

const loading = ref(false)
const error = ref(null)
const allUsers = ref([])
const addingUser = ref(false)
const busyUserId = ref(null)

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  },
})

const caseUsers = computed(() => props.caseData?.users || [])

const loadUsers = async () => {
  try {
    loading.value = true
    error.value = null
    allUsers.value = await userService.getUsers()
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to load users')
  } finally {
    loading.value = false
  }
}

const addUser = async (userId, isLead) => {
  try {
    addingUser.value = true
    error.value = null
    await caseService.addUserToCase(props.caseId, userId, isLead)
    emit('updated')
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to add user to case')
  } finally {
    addingUser.value = false
  }
}

const removeUser = async (user) => {
  if (!confirm(`Are you sure you want to remove ${user.email} from this case?`)) {
    return
  }

  try {
    busyUserId.value = user.id
    error.value = null
    await caseService.removeUserFromCase(props.caseId, user.id)
    emit('updated')
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to remove user from case')
  } finally {
    busyUserId.value = null
  }
}

const toggleLeadStatus = async (user) => {
  try {
    busyUserId.value = user.id
    error.value = null
    await caseService.updateCaseUserLeadStatus(props.caseId, user.id, !user.is_lead)
    emit('updated')
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to update lead status')
  } finally {
    busyUserId.value = null
  }
}

watch(
  () => props.show,
  (show) => {
    if (show) loadUsers()
  },
)
</script>
