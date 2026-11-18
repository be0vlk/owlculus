<template>
  <v-dialog
    v-model="dialogVisible"
    aria-label="New Case"
    max-width="800px"
    :persistent="isSubmitting"
  >
    <v-card>
      <v-card-title id="new-case-dialog-title" class="d-flex align-center">
        <v-icon start>mdi-folder-plus</v-icon>
        New Case
      </v-card-title>

      <v-card-text>
        <v-alert v-if="submissionError" class="mb-4" type="error" variant="tonal">
          {{ submissionError }}
        </v-alert>

        <v-form ref="form" v-model="isFormValid" @submit.prevent="handleSubmit">
          <v-text-field
            v-model="formData.title"
            autofocus
            label="Title"
            :rules="[(v) => !!v || 'Title is required']"
            required
            class="mb-4"
          />

          <v-select
            v-model="formData.client_id"
            :items="clients"
            item-title="name"
            item-value="id"
            label="Client"
            :rules="[(v) => !!v || 'Client is required']"
            required
            class="mb-4"
          />

          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-body-large pb-2">
              <v-icon start>mdi-account-group</v-icon>
              Assign Users
            </v-card-title>

            <v-card-text>
              <CaseUserList
                :users="selectedUsers"
                :all-users="allUsers"
                @add="addUser"
                @toggle-lead="(user) => (user.is_lead = !user.is_lead)"
                @remove="removeUser"
              />
            </v-card-text>
          </v-card>

          <v-switch
            v-if="strixy"
            v-model="strixyEnabled"
            label="Enable Strixy"
            hint="Let the Strixy AI assistant read this case"
            persistent-hint
            color="primary"
            inset
          />
        </v-form>
      </v-card-text>

      <ModalActions
        submit-text="Create Case"
        loading-text="Creating..."
        submit-icon="mdi-folder-plus"
        :submit-disabled="!isFormValid"
        :loading="isSubmitting"
        @cancel="cancelModal"
        @submit="handleSubmit"
      />
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { clientService } from '../services/client'
import { caseService } from '../services/case'
import { userService } from '../services/user'
import { useAuthStore } from '../stores/auth'
import { useDialogFocusRestore } from '../composables/useDialogFocusRestore'
import { getErrorMessage } from '../utils/errorMessage'
import { isStrixy } from '../utils/userDisplay'
import ModalActions from './ModalActions.vue'
import CaseUserList from './CaseUserList.vue'

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true,
  },
})

useDialogFocusRestore(() => props.isOpen)

const dialogVisible = computed({
  get: () => props.isOpen,
  set: (value) => {
    if (!value) {
      closeModal()
    }
  },
})

const emit = defineEmits(['close', 'created'])

const authStore = useAuthStore()
const clients = ref([])
const allUsers = ref([])
const selectedUsers = ref([])
const strixy = computed(() => allUsers.value.find(isStrixy))
const strixyEnabled = ref(false)
const isSubmitting = ref(false)
const submissionError = ref('')
const isFormValid = ref(false)
const form = ref(null)
const formData = reactive({
  title: '',
  client_id: '',
  status: 'Open',
})

const loadClients = async () => {
  if (!authStore.requiresAdmin()) {
    return
  }

  try {
    clients.value = await clientService.getClients()
    if (clients.value.length === 1 && !formData.client_id) formData.client_id = clients.value[0].id
  } catch (error) {
    console.error('Error loading clients:', error)
  }
}

const loadUsers = async () => {
  try {
    allUsers.value = await userService.getUsers()
  } catch (error) {
    console.error('Error loading users:', error)
  }
}

const addUser = (userId, isLead) => {
  selectedUsers.value.push({ ...allUsers.value.find((u) => u.id === userId), is_lead: isLead })
}

const removeUser = (user) => {
  selectedUsers.value = selectedUsers.value.filter((u) => u.id !== user.id)
}

const closeModal = () => {
  formData.title = ''
  formData.client_id = ''
  formData.status = 'Open'
  selectedUsers.value = []
  strixyEnabled.value = false
  submissionError.value = ''
  if (form.value) {
    form.value.reset()
  }
  emit('close')
}

const cancelModal = () => {
  if (!isSubmitting.value) closeModal()
}

const handleSubmit = async () => {
  if (!form.value || isSubmitting.value) return

  const { valid } = await form.value.validate()
  if (!valid) return

  isSubmitting.value = true
  submissionError.value = ''

  try {
    const newCase = await caseService.createCase(formData)
    const assignments = strixyEnabled.value
      ? [...selectedUsers.value, { id: strixy.value.id, is_lead: false }]
      : selectedUsers.value
    const assignmentResults = await Promise.allSettled(
      assignments.map((user) => caseService.addUserToCase(newCase.id, user.id, user.is_lead)),
    )
    const failedAssignments = assignmentResults.filter((result) => result.status === 'rejected')
    const assignmentWarning = failedAssignments.length
      ? `${failedAssignments.length} user assignment${failedAssignments.length === 1 ? '' : 's'} failed: ${getErrorMessage(failedAssignments[0].reason, 'assignment service unavailable')}`
      : null

    emit('created', newCase, { assignmentWarning })
    closeModal()
  } catch (error) {
    console.error('Error creating case:', error)
    submissionError.value = getErrorMessage(error, 'Failed to create case')
  } finally {
    isSubmitting.value = false
  }
}

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      loadClients()
      loadUsers()
    }
  },
  { immediate: true },
)
</script>
