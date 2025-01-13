<template>
  <div class="min-h-screen bg-gray-100 dark:bg-gray-900">
    <div class="flex">
      <!-- Sidebar -->
      <Sidebar class="fixed inset-y-0 left-0" />

      <!-- Main content -->
      <div class="flex-1 ml-64">
        <header class="bg-white shadow dark:bg-gray-800">
          <div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
            <h1 class="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">Settings</h1>
          </div>
        </header>
        <main class="mx-auto max-w-7xl py-6 sm:px-6 lg:px-8">
          <!-- Password Reset Section -->
          <div class="bg-white shadow sm:rounded-lg dark:bg-gray-800">
            <div class="px-4 py-5 sm:p-6">
              <h3 class="text-base font-semibold leading-6 text-gray-900 dark:text-white">Change Password</h3>
              <div class="mt-2 max-w-xl text-sm text-gray-500 dark:text-gray-300">
                <p>Update your password by entering your current password and a new password.</p>
              </div>
              <form @submit.prevent="handlePasswordChange" class="mt-5">
                <div class="space-y-4">
                  <div>
                    <label for="current-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      Current Password
                    </label>
                    <div class="mt-1">
                      <input
                        id="current-password"
                        v-model="currentPassword"
                        type="password"
                        required
                        :disabled="isLoading"
                        class="block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-500 focus:ring-cyan-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white text-gray-900"
                      />
                    </div>
                  </div>
                  <div>
                    <label for="new-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      New Password
                    </label>
                    <div class="mt-1">
                      <input
                        id="new-password"
                        v-model="newPassword"
                        type="password"
                        required
                        :disabled="isLoading"
                        class="block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-500 focus:ring-cyan-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white text-gray-900"
                      />
                    </div>
                  </div>
                  <div>
                    <label for="confirm-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      Confirm New Password
                    </label>
                    <div class="mt-1">
                      <input
                        id="confirm-password"
                        v-model="confirmPassword"
                        type="password"
                        required
                        :disabled="isLoading"
                        class="block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-500 focus:ring-cyan-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white text-gray-900"
                      />
                    </div>
                  </div>
                </div>

                <div v-if="error" class="mt-4 rounded-md bg-red-50 p-4 dark:bg-red-900">
                  <div class="flex">
                    <div class="flex-shrink-0">
                      <svg class="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                      </svg>
                    </div>
                    <div class="ml-3">
                      <h3 class="text-sm font-medium text-red-800 dark:text-red-200">{{ error }}</h3>
                    </div>
                  </div>
                </div>

                <div v-if="success" class="mt-4 rounded-md bg-green-50 p-4 dark:bg-green-900">
                  <div class="flex">
                    <div class="flex-shrink-0">
                      <svg class="h-5 w-5 text-green-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                      </svg>
                    </div>
                    <div class="ml-3">
                      <h3 class="text-sm font-medium text-green-800 dark:text-green-200">Password updated successfully</h3>
                    </div>
                  </div>
                </div>

                <div class="mt-5">
                  <button
                    type="submit"
                    :disabled="isLoading"
                    class="inline-flex items-center rounded-md border border-transparent bg-cyan-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 disabled:opacity-50"
                  >
                    {{ isLoading ? 'Updating...' : 'Update Password' }}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </main>
      </div>
    </div>
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
      new_password: newPassword.value
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
