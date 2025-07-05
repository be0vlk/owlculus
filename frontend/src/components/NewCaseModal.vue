<template>
  <v-dialog v-model="dialogVisible" max-width="800px" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-folder-plus</v-icon>
        New Case
      </v-card-title>

      <v-card-text>
        <v-form ref="form" v-model="isFormValid" @submit.prevent="handleSubmit">
          <v-text-field
            v-model="formData.title"
            label="Title"
            variant="outlined"
            density="comfortable"
            :rules="[(v) => !!v || 'Title is required']"
            required
            class="mb-4"
          />

          <v-select
            v-model="formData.client_id"
            :items="clientOptions"
            item-title="name"
            item-value="id"
            label="Client"
            variant="outlined"
            density="comfortable"
            :rules="[(v) => !!v || 'Client is required']"
            required
            class="mb-4"
          />

          <!-- Add Users Section -->
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 pb-2">
              <v-icon start>mdi-account-group</v-icon>
              Assign Users
            </v-card-title>

            <v-card-text>
              <!-- Selected Users -->
              <v-list v-if="selectedUsers.length > 0" density="compact" class="mb-4">
                <v-list-item
                  v-for="user in selectedUsers"
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
                    <v-icon
                      v-if="user.is_lead"
                      class="ml-1"
                      color="primary"
                      size="x-small"
                    >
                      mdi-star
                    </v-icon>
                    <v-chip
                      v-if="user.role === 'Analyst'"
                      class="ml-2"
                      color="grey"
                      size="x-small"
                      variant="tonal"
                    >
                      {{ user.role }}
                    </v-chip>
                  </v-list-item-title>
                  <v-list-item-subtitle>{{ user.username }}</v-list-item-subtitle>

                  <template #append>
                    <div class="d-flex align-center ga-1">
                      <v-tooltip
                        :text="getLeadButtonTooltip(user)"
                        location="top"
                      >
                        <template #activator="{ props }">
                          <v-btn
                            :color="user.is_lead ? 'primary' : 'default'"
                            :icon="user.is_lead ? 'mdi-star' : 'mdi-star-outline'"
                            :disabled="user.role === 'Analyst' && !user.is_lead"
                            size="small"
                            v-bind="props"
                            variant="text"
                            @click="toggleLeadStatus(user)"
                          />
                        </template>
                      </v-tooltip>

                      <v-tooltip location="top" text="Remove from selection">
                        <template #activator="{ props }">
                          <v-btn
                            color="error"
                            icon="mdi-close"
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

              <!-- Add User Form -->
              <v-row align="center">
                <v-col cols="12" md="6">
                  <v-select
                    v-model="userToAdd"
                    :items="availableUsers"
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
                    v-model="isLeadToAdd"
                    density="comfortable"
                    hide-details
                    label="Set as Lead"
                    :disabled="isUserToAddAnalyst"
                  />
                </v-col>
                <v-col cols="12" md="3">
                  <v-btn
                    :disabled="!userToAdd"
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

              <v-alert
                v-if="availableUsers.length === 0"
                class="mt-4"
                icon="mdi-information"
                type="info"
                variant="tonal"
              >
                <v-alert-title>No Users Available</v-alert-title>
                All users have been selected
              </v-alert>
            </v-card-text>
          </v-card>
        </v-form>
      </v-card-text>

      <ModalActions
        submit-text="Create Case"
        loading-text="Creating..."
        submit-icon="mdi-folder-plus"
        :submit-disabled="!isFormValid"
        :loading="isSubmitting"
        @cancel="closeModal"
        @submit="handleSubmit"
      />
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { clientService } from '../services/client'
import { caseService } from '../services/case'
import { userService } from '../services/user'
import { useAuthStore } from '../stores/auth'
import ModalActions from './ModalActions.vue'

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true,
  },
})

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
const userToAdd = ref(null)
const isLeadToAdd = ref(false)
const isSubmitting = ref(false)
const isFormValid = ref(false)
const form = ref(null)
const formData = reactive({
  title: '',
  client_id: '',
  status: 'Open',
})

const clientOptions = computed(() => clients.value)

const availableUsers = computed(() => {
  const selectedUserIds = selectedUsers.value.map(u => u.id)
  return allUsers.value
    .filter(user => !selectedUserIds.includes(user.id))
    .map(user => ({
      ...user,
      displayText: `${user.email} - ${user.username} (${user.role})`,
    }))
})

const isUserToAddAnalyst = computed(() => {
  if (!userToAdd.value) return false
  const user = allUsers.value.find(u => u.id === userToAdd.value)
  return user?.role === 'Analyst'
})

const loadClients = async () => {
  // Only load clients if user is admin
  if (!authStore.requiresAdmin()) {
    return
  }

  try {
    clients.value = await clientService.getClients()
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

// Auto-select client when only one exists
watch(clients, (newClients) => {
  if (newClients && newClients.length === 1 && !formData.client_id) {
    formData.client_id = newClients[0].id
  }
})

// Watch for user selection to reset isLead for analysts
watch(userToAdd, (newUserId) => {
  if (newUserId && isUserToAddAnalyst.value) {
    isLeadToAdd.value = false
  }
})

const addUser = () => {
  if (!userToAdd.value) return
  
  const user = allUsers.value.find(u => u.id === userToAdd.value)
  if (user) {
    selectedUsers.value.push({
      ...user,
      is_lead: isLeadToAdd.value && user.role !== 'Analyst'
    })
    
    // Reset form
    userToAdd.value = null
    isLeadToAdd.value = false
  }
}

const removeUser = (user) => {
  selectedUsers.value = selectedUsers.value.filter(u => u.id !== user.id)
}

const toggleLeadStatus = (user) => {
  // Don't allow toggle if user is an analyst and not currently a lead
  if (user.role === 'Analyst' && !user.is_lead) {
    return
  }
  
  const index = selectedUsers.value.findIndex(u => u.id === user.id)
  if (index !== -1) {
    selectedUsers.value[index].is_lead = !selectedUsers.value[index].is_lead
  }
}

const getLeadButtonTooltip = (user) => {
  if (user.role === 'Analyst' && !user.is_lead) {
    return 'Analysts cannot be set as leads'
  }
  return user.is_lead ? 'Remove as Lead' : 'Set as Lead'
}

const closeModal = () => {
  // Reset form
  formData.title = ''
  formData.client_id = ''
  formData.status = 'Open'
  selectedUsers.value = []
  userToAdd.value = null
  isLeadToAdd.value = false
  if (form.value) {
    form.value.reset()
  }
  emit('close')
}

const handleSubmit = async () => {
  const { valid } = await form.value.validate()
  if (!valid) return

  try {
    isSubmitting.value = true
    const newCase = await caseService.createCase(formData)
    
    // Add users to the case
    for (const user of selectedUsers.value) {
      await caseService.addUserToCase(newCase.id, user.id, user.is_lead)
    }
    
    emit('created', newCase)
    closeModal()
  } catch (error) {
    console.error('Error creating case:', error)
    // TODO: Add proper error handling UI
  } finally {
    isSubmitting.value = false
  }
}

// Load data when modal opens
watch(
  () => props.isOpen,
  (newVal) => {
    if (newVal) {
      loadClients()
      loadUsers()
    }
  },
)

onMounted(() => {
  if (props.isOpen) {
    loadClients()
    loadUsers()
  }
})
</script>
