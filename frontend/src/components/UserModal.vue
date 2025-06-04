<template>
  <v-dialog v-model="dialogVisible" max-width="500px" persistent>
    <v-card>
      <v-card-title>
        <span class="text-h5">{{ user ? 'Edit User' : 'Add New User' }}</span>
      </v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" class="mb-4">
          {{ error }}
        </v-alert>
        <v-form @submit.prevent="handleSubmit">
      <!-- Username -->
      <div>
        <label for="username" class="block text-sm font-medium mb-1">Username</label>
        <v-text-field
          id="username"
          v-model="formData.username"
          :disabled="!!user"
          variant="outlined"
          density="comfortable"
          required
        />
      </div>

      <!-- Email -->
      <div>
        <label for="email" class="block text-sm font-medium mb-1">Email</label>
        <v-text-field
          id="email"
          v-model="formData.email"
          type="email"
          variant="outlined"
          density="comfortable"
          required
        />
      </div>

      <!-- Password (only for new users) -->
      <div v-if="!user">
        <label for="password" class="block text-sm font-medium mb-1">Password</label>
        <v-text-field
          id="password"
          v-model="formData.password"
          type="password"
          variant="outlined"
          density="comfortable"
          required
        />
      </div>

      <!-- Role -->
      <div>
        <label for="role" class="block text-sm font-medium mb-1">Role</label>
        <v-select
          id="role"
          v-model="formData.role"
          :items="[
            { value: 'Analyst', title: 'Analyst' },
            { value: 'Investigator', title: 'Investigator' },
            { value: 'Admin', title: 'Admin' }
          ]"
          item-title="title"
          item-value="value"
          variant="outlined"
          density="comfortable"
          required
        />
      </div>
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="$emit('close')"
          :disabled="loading"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="handleSubmit"
          :disabled="loading"
          :loading="loading"
        >
          {{ loading ? 'Saving...' : (user ? 'Save Changes' : 'Create User') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { userService } from '../services/user'
// Vuetify components are auto-imported

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

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
})

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
