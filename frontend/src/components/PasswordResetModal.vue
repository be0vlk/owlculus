<template>
  <v-dialog
    aria-label="Reset Password"
    :model-value="show"
    max-width="500px"
    persistent
    @update:model-value="!$event && $emit('close')"
  >
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-warning">
        <v-icon start color="white" size="large">mdi-key-variant</v-icon>
        <div class="text-white">
          <div class="text-headline-small font-weight-bold">Reset Password</div>
          <div class="text-title-small text-yellow-lighten-2">
            Set a new password for this user account
          </div>
        </div>
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-6">
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
          {{ error }}
        </v-alert>

        <v-form
          :id="formId"
          v-model="valid"
          :disabled="loading"
          ref="formRef"
          @submit.prevent="handlePasswordReset"
        >
          <v-container fluid class="pa-0">
            <v-row>
              <v-col cols="12">
                <v-text-field
                  v-model="newPassword"
                  label="New Password"
                  :type="showNewPassword ? 'text' : 'password'"
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
                  <div class="text-body-medium" :class="`text-${passwordStrength.color}`">
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

      <modal-actions
        :submit-form="formId"
        submit-text="Reset Password"
        submit-icon="mdi-key-variant"
        submit-color="warning"
        :submit-disabled="!valid"
        :loading="loading"
        @cancel="$emit('close')"
        @submit="handlePasswordReset"
      />
    </v-card>
  </v-dialog>
</template>

<script setup>
import { useId, ref, computed } from 'vue'
import { userService } from '@/services/user'
import ModalActions from './ModalActions.vue'

const props = defineProps({
  show: {
    type: Boolean,
    required: true,
  },
  userId: {
    type: Number,
    required: false,
    default: null,
  },
})

const emit = defineEmits(['close', 'saved'])

const newPassword = ref('')
const confirmPassword = ref('')
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)
const loading = ref(false)
const error = ref('')
const valid = ref(false)
const formId = useId()
const formRef = ref(null)

// One check set drives the rules, the requirement chips and the strength meter.
const REQUIREMENTS = [
  {
    text: '8+ characters',
    message: 'Password must be at least 8 characters',
    test: (v) => v.length >= 8,
  },
  {
    text: 'Contains letter',
    message: 'Password must contain at least one letter',
    test: (v) => /[A-Za-z]/.test(v),
  },
  {
    text: 'Contains number',
    message: 'Password must contain at least one number',
    test: (v) => /\d/.test(v),
  },
]

const passwordRules = [
  (v) => !!v || 'Password is required',
  ...REQUIREMENTS.map(
    ({ message, test }) =>
      (v) =>
        test(v) || message,
  ),
]

const confirmPasswordRules = [
  (v) => !!v || 'Please confirm your password',
  (v) => v === newPassword.value || 'Passwords do not match',
]

const passwordRequirements = computed(() => [
  ...REQUIREMENTS.map(({ text, test }) => ({ text, met: test(newPassword.value) })),
  { text: 'Passwords match', met: newPassword.value === confirmPassword.value },
])

const STRENGTH = [
  { label: 'Very Weak', color: 'error' },
  { label: 'Weak', color: 'error' },
  { label: 'Fair', color: 'warning' },
  { label: 'Good', color: 'success' },
  { label: 'Strong', color: 'success' },
]
const passwordStrength = computed(() => {
  const password = newPassword.value
  const special = /[!@#$%^&*(),.?":{}|<>]/.test(password) ? 1 : 0
  const score = REQUIREMENTS.filter(({ test }) => test(password)).length + special
  return { score, ...STRENGTH[score] }
})

const handlePasswordReset = async () => {
  if (loading.value || !props.userId) return
  const { valid } = await formRef.value.validate()
  if (!valid || loading.value) return

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
