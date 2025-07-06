<!-- eslint-disable vue/multi-word-component-names -->
<template>
  <div>
    <Sidebar />

    <v-main>
      <v-container class="pa-6">
        <!-- Page Header -->
        <div class="mb-6">
          <v-row align="center" justify="space-between">
            <v-col>
              <h1 class="text-h4 font-weight-bold">Settings</h1>
            </v-col>
          </v-row>
        </div>

        <!-- Password Reset Section -->
        <v-card>
          <v-card-title>
            <span class="text-h5">Change Password</span>
          </v-card-title>
          <v-card-text>
            <p class="text-body-2 mb-6">
              Update your password by entering your current password and a new password.
            </p>

            <v-form @submit.prevent="handlePasswordChange">
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="currentPassword"
                    label="Current Password"
                    type="password"
                    variant="outlined"
                    :disabled="isLoading"
                    required
                    class="mb-4"
                  />

                  <v-text-field
                    v-model="newPassword"
                    label="New Password"
                    type="password"
                    variant="outlined"
                    :disabled="isLoading"
                    required
                    class="mb-4"
                  />

                  <v-text-field
                    v-model="confirmPassword"
                    label="Confirm New Password"
                    type="password"
                    variant="outlined"
                    :disabled="isLoading"
                    required
                    class="mb-4"
                  />

                  <!-- Error Alert -->
                  <v-alert v-if="error" :text="error" class="mb-4" type="error" />

                  <!-- Success Alert -->
                  <v-alert
                    v-if="success"
                    type="success"
                    class="mb-4"
                    text="Password updated successfully"
                  />

                  <v-btn
                    type="submit"
                    color="primary"
                    :loading="isLoading"
                    :disabled="isLoading"
                    size="large"
                  >
                    {{ isLoading ? 'Updating...' : 'Update Password' }}
                  </v-btn>
                </v-col>
              </v-row>
            </v-form>
          </v-card-text>
        </v-card>
      </v-container>
    </v-main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import Sidebar from '../components/Sidebar.vue'

const authStore = useAuthStore()

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const isLoading = ref(false)
const error = ref(null)
const success = ref(false)

const handlePasswordChange = async () => {
  error.value = null
  success.value = false

  if (newPassword.value !== confirmPassword.value) {
    error.value = 'New passwords do not match'
    return
  }

  try {
    isLoading.value = true
    await authStore.changePassword({
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    success.value = true
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to update password'
  } finally {
    isLoading.value = false
  }
}
</script>
