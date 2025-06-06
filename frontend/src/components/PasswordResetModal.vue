<template>
  <v-dialog v-model="dialogVisible" max-width="500px" persistent>
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-warning">
        <v-icon start color="white" size="large">mdi-key-variant</v-icon>
        <div class="text-white">
          <div class="text-h5 font-weight-bold">Reset Password</div>
          <div class="text-subtitle-2 text-yellow-lighten-2">
            Set a new password for this user account
          </div>
        </div>
      </v-card-title>
      
      <v-divider />
      
      <v-card-text class="pa-6">
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
          {{ error }}
        </v-alert>
        
        <v-form ref="formRef" @submit.prevent="handlePasswordReset">
          <v-container fluid class="pa-0">
            <v-row>
              <v-col cols="12">
                <v-text-field
                  v-model="newPassword"
                  label="New Password"
                  :type="showNewPassword ? 'text' : 'password'"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-lock"
                  :append-inner-icon="showNewPassword ? 'mdi-eye' : 'mdi-eye-off'"
                  @click:append-inner="showNewPassword = !showNewPassword"
                  :rules="passwordRules"
                  required
                  hint="Minimum 8 characters with letters and numbers"
                  persistent-hint
                />
              </v-col>
              
              <v-col cols="12">
                <v-text-field
                  v-model="confirmPassword"
                  label="Confirm Password"
                  :type="showConfirmPassword ? 'text' : 'password'"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-lock-check"
                  :append-inner-icon="showConfirmPassword ? 'mdi-eye' : 'mdi-eye-off'"
                  @click:append-inner="showConfirmPassword = !showConfirmPassword"
                  :rules="confirmPasswordRules"
                  required
                  hint="Must match the password above"
                  persistent-hint
                />
              </v-col>
              
              <!-- Password strength indicator -->
              <v-col cols="12" v-if="newPassword">
                <v-card variant="outlined" class="pa-3">
                  <v-card-subtitle class="pa-0 pb-2">
                    <v-icon icon="mdi-shield-check" size="small" class="me-2" />
                    Password Strength
                  </v-card-subtitle>
                  <v-progress-linear
                    :model-value="passwordStrength.score * 25"
                    :color="passwordStrength.color"
                    height="8"
                    rounded
                    class="mb-2"
                  />
                  <div class="text-body-2" :class="`text-${passwordStrength.color}`">
                    {{ passwordStrength.label }}
                  </div>
                  <div class="mt-2">
                    <v-chip
                      v-for="requirement in passwordRequirements"
                      :key="requirement.text"
                      :color="requirement.met ? 'success' : 'grey'"
                      :variant="requirement.met ? 'tonal' : 'outlined'"
                      size="small"
                      class="ma-1"
                    >
                      <v-icon start :icon="requirement.met ? 'mdi-check' : 'mdi-close'" />
                      {{ requirement.text }}
                    </v-chip>
                  </div>
                </v-card>
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
          @click="$emit('close')"
          :disabled="loading"
        >
          Cancel
        </v-btn>
        <v-btn
          color="warning"
          variant="flat"
          prepend-icon="mdi-key-variant"
          @click="handlePasswordReset"
          :disabled="!isPasswordValid || loading"
          :loading="loading"
        >
          {{ loading ? 'Resetting...' : 'Reset Password' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
// Vuetify components are auto-imported
import { userService } from '@/services/user'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  userId: {
    type: Number,
    required: false,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
})

const newPassword = ref('')
const confirmPassword = ref('')
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)
const loading = ref(false)
const error = ref('')
const formRef = ref(null)

// Validation rules
const passwordRules = [
  v => !!v || 'Password is required',
  v => v.length >= 8 || 'Password must be at least 8 characters',
  v => /[A-Za-z]/.test(v) || 'Password must contain at least one letter',
  v => /\d/.test(v) || 'Password must contain at least one number'
]

const confirmPasswordRules = [
  v => !!v || 'Please confirm your password',
  v => v === newPassword.value || 'Passwords do not match'
]

// Password requirements tracking
const passwordRequirements = computed(() => [
  {
    text: '8+ characters',
    met: newPassword.value.length >= 8
  },
  {
    text: 'Contains letter',
    met: /[A-Za-z]/.test(newPassword.value)
  },
  {
    text: 'Contains number',
    met: /\d/.test(newPassword.value)
  },
  {
    text: 'Passwords match',
    met: newPassword.value && confirmPassword.value && newPassword.value === confirmPassword.value
  }
])

// Password strength calculation
const passwordStrength = computed(() => {
  const password = newPassword.value
  if (!password) return { score: 0, label: 'Enter a password', color: 'grey' }
  
  let score = 0
  const checks = [
    password.length >= 8,
    /[A-Za-z]/.test(password),
    /\d/.test(password),
    /[!@#$%^&*(),.?":{}|<>]/.test(password)
  ]
  
  score = checks.filter(Boolean).length
  
  const strengthMap = {
    0: { label: 'Very Weak', color: 'error' },
    1: { label: 'Weak', color: 'error' },
    2: { label: 'Fair', color: 'warning' },
    3: { label: 'Good', color: 'success' },
    4: { label: 'Strong', color: 'success' }
  }
  
  return { score, ...strengthMap[score] }
})

const isPasswordValid = computed(() => {
  return newPassword.value && 
         confirmPassword.value && 
         newPassword.value === confirmPassword.value &&
         newPassword.value.length >= 8 &&
         /[A-Za-z]/.test(newPassword.value) &&
         /\d/.test(newPassword.value)
})

const handlePasswordReset = async () => {
  if (!isPasswordValid.value || !props.userId) return

  loading.value = true
  error.value = ''

  try {
    await userService.resetPassword(props.userId, newPassword.value)
    newPassword.value = ''
    confirmPassword.value = ''
    showNewPassword.value = false
    showConfirmPassword.value = false
    emit('saved')
  } catch (err) {
    console.error('Error resetting password:', err)
    error.value = err.response?.data?.detail || 'Failed to reset password. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>
