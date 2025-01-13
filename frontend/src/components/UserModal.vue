<template>
  <div v-if="show" class="fixed inset-0 z-10 overflow-y-auto">
    <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
      <!-- Background overlay -->
      <div class="fixed inset-0 transition-opacity" aria-hidden="true">
        <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
      </div>

      <!-- Modal panel -->
      <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
        <form @submit.prevent="handleSubmit">
          <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <div class="mb-4">
              <h3 class="text-lg font-medium leading-6 text-gray-900">
                {{ user ? 'Edit User' : 'Add New User' }}
              </h3>
            </div>

            <!-- Error message -->
            <div v-if="error" class="mb-4 bg-red-50 border-l-4 border-red-400 p-4">
              <div class="flex">
                <div class="flex-shrink-0">
                  <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                  </svg>
                </div>
                <div class="ml-3">
                  <p class="text-sm text-red-700">{{ error }}</p>
                </div>
              </div>
            </div>

            <div class="space-y-4">
              <!-- Username -->
              <div>
                <label for="username" class="block text-sm font-medium text-gray-700">Username</label>
                <input
                  type="text"
                  id="username"
                  v-model="formData.username"
                  :disabled="!!user"
                  class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-300 focus:ring focus:ring-cyan-200 focus:ring-opacity-50 disabled:bg-gray-100 text-gray-900"
                  required
                />
              </div>

              <!-- Email -->
              <div>
                <label for="email" class="block text-sm font-medium text-gray-700">Email</label>
                <input
                  type="email"
                  id="email"
                  v-model="formData.email"
                  class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-300 focus:ring focus:ring-cyan-200 focus:ring-opacity-50 text-gray-900"
                  required
                />
              </div>

              <!-- Password (only for new users) -->
              <div v-if="!user">
                <label for="password" class="block text-sm font-medium text-gray-700">Password</label>
                <input
                  type="password"
                  id="password"
                  v-model="formData.password"
                  class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-300 focus:ring focus:ring-cyan-200 focus:ring-opacity-50 text-gray-900"
                  required
                />
              </div>

              <!-- Role -->
              <div>
                <label for="role" class="block text-sm font-medium text-gray-700">Role</label>
                <select
                  id="role"
                  v-model="formData.role"
                  class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-300 focus:ring focus:ring-cyan-200 focus:ring-opacity-50 text-gray-900"
                  required
                >
                  <option value="Analyst">Analyst</option>
                  <option value="Investigator">Investigator</option>
                  <option value="Admin">Admin</option>
                </select>
              </div>
            </div>
          </div>

          <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
            <button
              type="submit"
              :disabled="loading"
              class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-cyan-600 text-base font-medium text-white hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50"
            >
              {{ loading ? 'Saving...' : (user ? 'Save Changes' : 'Create User') }}
            </button>
            <button
              type="button"
              @click="$emit('close')"
              :disabled="loading"
              class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { userService } from '../services/user'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  user: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])

const loading = ref(false)
const error = ref(null)
const formData = ref({
  username: '',
  email: '',
  password: '',
  role: 'Analyst',
  is_active: true
})

const resetForm = () => {
  formData.value = {
    username: '',
    email: '',
    password: '',
    role: 'Analyst',
    is_active: true
  }
}

onMounted(() => {
  if (props.user) {
    formData.value = {
      ...formData.value,
      ...props.user,
      password: '' // Don't include password when editing
    }
  }
})

const handleSubmit = async () => {
  try {
    loading.value = true
    error.value = null

    let result
    if (props.user) {
      // Update existing user
      result = await userService.updateUser(props.user.id, {
        email: formData.value.email,
        role: formData.value.role,
        is_active: formData.value.is_active
      })
    } else {
      // Create new user
      result = await userService.createUser({
        username: formData.value.username,
        email: formData.value.email,
        password: formData.value.password,
        role: formData.value.role,
        is_active: true
      })
    }

    emit('saved', result)
    resetForm() // Reset form before closing
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to save user. Please try again.'
    console.error('Error saving user:', err)
  } finally {
    loading.value = false
  }
}
</script>
