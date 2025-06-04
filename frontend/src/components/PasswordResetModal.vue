<template>
  <v-dialog v-model="dialogVisible" max-width="400px" persistent>
    <v-card>
      <v-card-title>
        <span class="text-h5">Reset Password</span>
      </v-card-title>
      <v-card-text>
        <v-form>
          <v-text-field
            v-model="newPassword"
            label="New Password"
            type="password"
            variant="outlined"
            density="comfortable"
          />
          <v-text-field
            v-model="confirmPassword"
            label="Confirm Password"
            type="password"
            variant="outlined"
            density="comfortable"
          />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="$emit('close')"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="handlePasswordReset"
          :disabled="!isPasswordValid"
        >
          Reset Password
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

const isPasswordValid = computed(() => {
  return newPassword.value && 
         confirmPassword.value && 
         newPassword.value === confirmPassword.value &&
         newPassword.value.length >= 8
})

const handlePasswordReset = async () => {
  if (!isPasswordValid.value || !props.userId) return

  try {
    await userService.resetPassword(props.userId, newPassword.value)
    newPassword.value = ''
    confirmPassword.value = ''
    emit('saved')
  } catch (error) {
    console.error('Error resetting password:', error)
    const errorMessage = error.response?.data?.detail || 'Failed to reset password. Please try again.'
    alert(errorMessage)
  }
}
</script>
