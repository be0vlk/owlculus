<template>
  <v-dialog v-model="dialogVisible" max-width="500px" persistent scrollable>
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-primary">
        <v-icon start color="white" size="large">mdi-email-plus</v-icon>
        <div class="text-white">
          <div class="text-h5 font-weight-bold">Generate Invite</div>
          <div class="text-subtitle-2 text-blue-lighten-2">
            Create a new user invitation link
          </div>
        </div>
      </v-card-title>
      
      <v-divider />
      
      <v-card-text class="pa-6">
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
          {{ error }}
        </v-alert>
        
        <v-alert v-if="successMessage" type="success" variant="tonal" class="mb-4">
          {{ successMessage }}
        </v-alert>
        
        <v-form ref="formRef" @submit.prevent="handleSubmit">
          <v-container fluid class="pa-0">
            <v-row>
              <!-- Role Selection -->
              <v-col cols="12">
                <v-select
                  v-model="formData.role"
                  :items="roleOptions"
                  item-title="title"
                  item-value="value"
                  label="User Role"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-shield-account"
                  required
                  hint="Select the role for the new user account"
                  persistent-hint
                >
                  <template #item="{ props, item }">
                    <v-list-item v-bind="props">
                      <template #prepend>
                        <v-icon :icon="item.raw.icon" :color="item.raw.color" />
                      </template>
                      <v-list-item-title>{{ item.raw.title }}</v-list-item-title>
                      <v-list-item-subtitle>{{ item.raw.description }}</v-list-item-subtitle>
                    </v-list-item>
                  </template>
                </v-select>
              </v-col>

              <!-- Invite Link Display (when created) -->
              <v-col cols="12" v-if="inviteLink">
                <v-text-field
                  :model-value="inviteLink"
                  label="Invite Link"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-link"
                  readonly
                  append-inner-icon="mdi-content-copy"
                  @click:append-inner="copyToClipboard"
                  hint="Share this link with the new user. It expires in 48 hours."
                  persistent-hint
                />
              </v-col>
            </v-row>
          </v-container>
        </v-form>
      </v-card-text>

      <v-divider />
      
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn
          variant="text"
          prepend-icon="mdi-close"
          @click="handleClose"
          :disabled="loading"
        >
          {{ inviteLink ? 'Done' : 'Cancel' }}
        </v-btn>
        <v-btn
          v-if="!inviteLink"
          color="primary"
          variant="flat"
          prepend-icon="mdi-email-plus"
          @click="handleSubmit"
          :disabled="loading || !isFormValid"
          :loading="loading"
        >
          {{ loading ? 'Generating...' : 'Generate Invite' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { inviteService } from '../services/invite'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['close', 'created'])

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      handleClose()
    }
  }
})

const loading = ref(false)
const error = ref(null)
const successMessage = ref(null)
const inviteLink = ref(null)
const formRef = ref(null)

const formData = ref({
  role: 'Analyst'
})

const roleOptions = [
  {
    value: 'Analyst',
    title: 'Analyst',
    description: 'Read-only access to assigned cases',
    icon: 'mdi-chart-line',
    color: 'info'
  },
  {
    value: 'Investigator',
    title: 'Investigator',
    description: 'Read/write access, can run plugins',
    icon: 'mdi-account-search',
    color: 'primary'
  },
  {
    value: 'Admin',
    title: 'Administrator',
    description: 'Full system access and user management',
    icon: 'mdi-shield-check',
    color: 'error'
  }
]

const isFormValid = computed(() => {
  return !!formData.value.role
})

const resetForm = () => {
  formData.value = { role: 'Analyst' }
  error.value = null
  successMessage.value = null
  inviteLink.value = null
}

const handleClose = () => {
  resetForm()
  emit('close')
}

const copyToClipboard = async () => {
  try {
    await navigator.clipboard.writeText(inviteLink.value)
    successMessage.value = 'Invite link copied to clipboard!'
    setTimeout(() => {
      successMessage.value = null
    }, 3000)
  } catch {
    error.value = 'Failed to copy to clipboard'
  }
}

const handleSubmit = async () => {
  try {
    loading.value = true
    error.value = null
    successMessage.value = null

    const result = await inviteService.createInvite({
      role: formData.value.role
    })

    const baseUrl = window.location.origin
    inviteLink.value = `${baseUrl}/register?token=${result.token}`
    
    successMessage.value = 'Invite generated successfully!'
    emit('created', result)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to generate invite. Please try again.'
    console.error('Error creating invite:', err)
  } finally {
    loading.value = false
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    resetForm()
  }
})
</script>