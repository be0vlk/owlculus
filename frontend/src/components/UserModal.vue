<template>
  <v-dialog v-model="dialogVisible" max-width="600px" persistent scrollable>
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-primary">
        <v-icon start color="white" size="large">
          {{ user ? 'mdi-account-edit' : 'mdi-account-plus' }}
        </v-icon>
        <div class="text-white">
          <div class="text-h5 font-weight-bold">
            {{ user ? 'Edit User' : 'Add New User' }}
          </div>
          <div class="text-subtitle-2 text-blue-lighten-2">
            {{ user ? 'Update user information and permissions' : 'Create a new user account' }}
          </div>
        </div>
      </v-card-title>
      
      <v-divider />
      
      <v-card-text class="pa-6">
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
          {{ error }}
        </v-alert>
        
        <v-form ref="formRef" @submit.prevent="handleSubmit">
          <v-container fluid class="pa-0">
            <v-row>
              <!-- Username -->
              <v-col cols="12">
                <v-text-field
                  v-model="formData.username"
                  label="Username"
                  :disabled="!!user"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-account"
                  :rules="usernameRules"
                  required
                  :hint="user ? 'Username cannot be changed after creation' : 'Enter a unique username'"
                  :persistent-hint="!!user"
                />
              </v-col>

              <!-- Email -->
              <v-col cols="12">
                <v-text-field
                  v-model="formData.email"
                  label="Email Address"
                  type="email"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-email"
                  :rules="emailRules"
                  required
                  hint="User will receive notifications at this email"
                  persistent-hint
                />
              </v-col>

              <!-- Password (only for new users) -->
              <v-col cols="12" v-if="!user">
                <v-text-field
                  v-model="formData.password"
                  label="Password"
                  :type="showPassword ? 'text' : 'password'"
                  variant="outlined"
                  density="comfortable"
                  prepend-inner-icon="mdi-lock"
                  :append-inner-icon="showPassword ? 'mdi-eye' : 'mdi-eye-off'"
                  @click:append-inner="showPassword = !showPassword"
                  :rules="passwordRules"
                  required
                  hint="Minimum 8 characters with letters and numbers"
                  persistent-hint
                />
              </v-col>

              <!-- Role -->
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
                  hint="Determines user permissions and access level"
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
            </v-row>
          </v-container>
        </v-form>
      </v-card-text>

      <v-divider />
      
      <modal-actions
        :submit-text="user ? 'Save Changes' : 'Create User'"
        :submit-icon="user ? 'mdi-content-save' : 'mdi-account-plus'"
        :submit-disabled="!isFormValid"
        :loading="loading"
        @cancel="$emit('close')"
        @submit="handleSubmit"
      />
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { userService } from '../services/user'
// Vuetify components are auto-imported
import ModalActions from './ModalActions.vue'

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
const showPassword = ref(false)
const formRef = ref(null)

const formData = ref({
  username: '',
  email: '',
  password: '',
  role: 'Analyst',
  is_active: true
})

// Role options with descriptions and icons
const roleOptions = [
  {
    value: 'Analyst',
    title: 'Analyst',
    description: 'Read-only access to assigned cases',
    icon: 'mdi-chart-line',
    color: 'warning'
  },
  {
    value: 'Investigator',
    title: 'Investigator',
    description: 'Read/write access, can run plugins',
    icon: 'mdi-account-search',
    color: 'info'
  },
  {
    value: 'Admin',
    title: 'Administrator',
    description: 'Full system access and user management',
    icon: 'mdi-shield-check',
    color: 'success'
  }
]

// Validation rules
const usernameRules = [
  v => !!v || 'Username is required',
  v => v.length >= 3 || 'Username must be at least 3 characters',
  v => v.length <= 50 || 'Username must be less than 50 characters',
  v => /^[a-zA-Z0-9_-]+$/.test(v) || 'Username can only contain letters, numbers, underscore and dash'
]

const emailRules = [
  v => !!v || 'Email is required',
  v => /.+@.+\..+/.test(v) || 'Email must be valid'
]

const passwordRules = [
  v => !!v || 'Password is required',
  v => v.length >= 8 || 'Password must be at least 8 characters',
  v => /[A-Za-z]/.test(v) || 'Password must contain at least one letter',
  v => /\d/.test(v) || 'Password must contain at least one number'
]

// Form validation
const isFormValid = computed(() => {
  if (!formData.value.username || !formData.value.email || !formData.value.role) {
    return false
  }
  
  if (!props.user && !formData.value.password) {
    return false
  }
  
  // Check email format
  if (!/.+@.+\..+/.test(formData.value.email)) {
    return false
  }
  
  // Check username format
  if (formData.value.username.length < 3 || !/^[a-zA-Z0-9_-]+$/.test(formData.value.username)) {
    return false
  }
  
  // Check password for new users
  if (!props.user) {
    if (formData.value.password.length < 8 || 
        !/[A-Za-z]/.test(formData.value.password) || 
        !/\d/.test(formData.value.password)) {
      return false
    }
  }
  
  return true
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

const updateFormData = () => {
  if (props.user) {
    formData.value = {
      ...formData.value,
      ...props.user,
      password: '' // Don't include password when editing
    }
  } else {
    resetForm()
  }
}

onMounted(() => {
  updateFormData()
})

// Watch for changes to the user prop to update form data
watch(() => props.user, () => {
  updateFormData()
}, { immediate: true })

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
