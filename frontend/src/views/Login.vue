<!-- eslint-disable vue/multi-word-component-names -->
<template>
  <v-main>
    <v-container class="fill-height d-flex align-center justify-center" fluid>
      <v-row align="center" class="fill-height" justify="center">
        <v-col cols="12" lg="4" md="6" sm="8" xl="3">
          <v-card class="rounded-xl" elevation="8">
            <v-card-text class="pa-8">
              <!-- Logo -->
              <div class="text-center mb-8">
                <v-img
                  :src="isDark ? '/owl_logo_white.png' : '/owl_logo.png'"
                  alt="Owlculus Logo"
                  class="mx-auto"
                  contain
                  max-height="200"
                />
              </div>

              <!-- Login Form -->
              <v-form ref="form" @submit.prevent="handleLogin">
                <v-text-field
                  v-model="formData.username"
                  :disabled="isLoading"
                  class="mb-4"
                  label="Username"
                  prepend-inner-icon="mdi-account"
                  required
                  variant="outlined"
                />

                <v-text-field
                  v-model="formData.password"
                  :disabled="isLoading"
                  class="mb-6"
                  label="Password"
                  prepend-inner-icon="mdi-lock"
                  required
                  type="password"
                  variant="outlined"
                />

                <!-- Error Alert -->
                <v-alert v-if="error" :text="error" class="mb-4" type="error" />

                <!-- Login Button -->
                <v-btn
                  :disabled="isLoading"
                  :loading="isLoading"
                  block
                  class="text-none"
                  color="primary"
                  size="large"
                  type="submit"
                >
                  <v-icon start>mdi-login</v-icon>
                  {{ isLoading ? 'Signing in...' : 'Sign in' }}
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
import { useAuthStore } from '../stores/auth'
import { useDarkMode } from '../composables/useDarkMode'

const router = useRouter()
const authStore = useAuthStore()
const { isDark } = useDarkMode()
const isLoading = ref(false)
const error = ref(null)
const form = ref(null)
const formData = reactive({
  username: '',
  password: '',
})

async function handleLogin() {
  try {
    error.value = null
    isLoading.value = true
    await authStore.login(formData.username, formData.password)
    router.push('/cases')
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to sign in. Please check your credentials.'
  } finally {
    isLoading.value = false
  }
}
</script>
