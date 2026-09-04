<!-- eslint-disable vue/multi-word-component-names -->
<template>
  <v-main class="setup-page">
    <v-container class="fill-height d-flex align-center justify-center pa-4 pa-sm-6" fluid>
      <v-row class="fill-height align-center justify-center">
        <v-col cols="12" lg="5" md="7" sm="9" xl="4">
          <v-card class="rounded-xl mx-auto setup-card" elevation="3">
            <v-card-text class="pa-6 pa-sm-8">
              <div class="text-center mb-6">
                <v-img
                  :src="isDark ? '/owl_logo_white.png' : '/owl_logo.png'"
                  alt="Owlculus Logo"
                  class="mx-auto mb-6"
                  max-height="140"
                />
                <h1 class="text-headline-large font-weight-bold mb-2">Welcome to Owlculus</h1>
                <p class="text-body-large text-medium-emphasis">
                  Create your administrator account to get started
                </p>
              </div>

              <v-form @submit.prevent="handleSetup">
                <v-alert v-if="error" class="mb-5" type="error" variant="tonal">
                  {{ error }}
                </v-alert>

                <v-text-field
                  v-model="formData.setupToken"
                  :disabled="isLoading"
                  autofocus
                  class="mb-4"
                  label="Setup Token"
                  placeholder="Find this in the server console output."
                  prepend-inner-icon="mdi-key-variant"
                  required
                  variant="outlined"
                />

                <v-text-field
                  v-model="formData.username"
                  :disabled="isLoading"
                  autocomplete="username"
                  class="mb-4"
                  label="Username"
                  maxlength="50"
                  prepend-inner-icon="mdi-account"
                  required
                  variant="outlined"
                />

                <v-text-field
                  v-model="formData.email"
                  :disabled="isLoading"
                  autocomplete="email"
                  class="mb-4"
                  label="Email"
                  prepend-inner-icon="mdi-email"
                  required
                  type="email"
                  variant="outlined"
                />

                <v-text-field
                  v-model="formData.password"
                  :disabled="isLoading"
                  autocomplete="new-password"
                  class="mb-4"
                  label="Password"
                  prepend-inner-icon="mdi-lock"
                  required
                  type="password"
                  variant="outlined"
                />

                <v-text-field
                  v-model="formData.confirmPassword"
                  :disabled="isLoading"
                  autocomplete="new-password"
                  class="mb-6"
                  label="Confirm Password"
                  prepend-inner-icon="mdi-lock-check"
                  required
                  type="password"
                  variant="outlined"
                />

                <v-btn
                  :disabled="isLoading"
                  block
                  class="text-none"
                  color="primary"
                  size="large"
                  type="submit"
                >
                  {{ isLoading ? 'Creating account...' : 'Create Administrator Account' }}
                </v-btn>
              </v-form>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </v-main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDarkMode } from '../composables/useDarkMode'
import { authService } from '../services/auth'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const { isDark } = useDarkMode()
const isLoading = ref(false)
const error = ref(null)
const formData = reactive({
  setupToken: '',
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const reservedEmailSuffixes = ['local', 'localhost', 'invalid', 'example', 'test']

const isValidEmail = (email) => {
  if (!/.+@.+\..+/.test(email)) return false
  const domain = email.slice(email.lastIndexOf('@') + 1).toLowerCase()
  return !reservedEmailSuffixes.some((suffix) => domain === suffix || domain.endsWith(`.${suffix}`))
}

const validateForm = () => {
  if (!formData.setupToken) return 'Setup token is required'
  if (!formData.username) return 'Username is required'
  if (formData.username.length < 3 || formData.username.length > 50) {
    return 'Username must be between 3 and 50 characters'
  }
  if (!/^[A-Za-z0-9_]+$/.test(formData.username)) {
    return 'Username can only contain letters, numbers, and underscores'
  }
  if (!formData.email) return 'Email is required'
  if (!isValidEmail(formData.email)) return 'Please enter a valid email address'
  if (formData.password !== formData.confirmPassword) return 'Passwords do not match'
  if (formData.password.length < 10) return 'Password must be at least 10 characters'
  return null
}

const handleSetup = async () => {
  error.value = validateForm()
  if (error.value) return

  try {
    isLoading.value = true
    await authService.createAdministrator({
      setup_token: formData.setupToken,
      username: formData.username,
      email: formData.email,
      password: formData.password,
    })
    authStore.completeSetup()
    await router.push('/login')
  } catch (err) {
    error.value =
      err.response?.data?.detail ||
      (err.response ? 'Setup failed' : 'Setup failed. Please try again.')
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.setup-page {
  min-height: 100vh;
}

.setup-card {
  max-width: 520px;
}
</style>
