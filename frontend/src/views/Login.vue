<!-- eslint-disable vue/multi-word-component-names -->
<template>
  <div>
    <v-main>
      <v-container class="fill-height" fluid>
        <v-row align="center" justify="center">
          <v-col cols="12" sm="8" md="6" lg="4" xl="3">
            <v-card elevation="8" class="rounded-xl">
              <v-card-text class="pa-8">
                <!-- Logo -->
                <div class="text-center mb-8">
                  <v-img
                    :src="isDark ? '/owl_logo_white.png' : '/owl_logo.png'"
                    alt="Owlculus Logo"
                    max-height="200"
                    contain
                    class="mx-auto"
                  />
                </div>

                <!-- Login Form -->
                <v-form ref="form" @submit.prevent="handleLogin">
                  <v-text-field
                    v-model="formData.username"
                    label="Username"
                    prepend-inner-icon="mdi-account"
                    variant="outlined"
                    :disabled="isLoading"
                    required
                    class="mb-4"
                  />

                  <v-text-field
                    v-model="formData.password"
                    label="Password"
                    type="password"
                    prepend-inner-icon="mdi-lock"
                    variant="outlined"
                    :disabled="isLoading"
                    required
                    class="mb-6"
                  />

                  <!-- Error Alert -->
                  <v-alert
                    v-if="error"
                    type="error"
                    class="mb-4"
                    :text="error"
                  />

                  <!-- Login Button -->
                  <v-btn
                    type="submit"
                    color="primary"
                    size="large"
                    block
                    :loading="isLoading"
                    :disabled="isLoading"
                    class="text-none"
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
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
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
  password: ''
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