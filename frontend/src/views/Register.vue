<!-- eslint-disable vue/multi-word-component-names -->
<template>
  <div>
    <v-main>
      <v-container class="fill-height" fluid>
        <v-row class="align-center justify-center">
          <v-col cols="12" sm="8" md="6" lg="4" xl="3">
            <v-card elevation="3" class="rounded-xl">
              <v-card-text class="pa-8">
                <!-- Logo -->
                <div class="text-center mb-8">
                  <v-img
                    :src="isDark ? '/owl_logo_white.png' : '/owl_logo.png'"
                    alt="Owlculus Logo"
                    max-height="200"
                    class="mx-auto"
                  />
                </div>

                <!-- Title -->
                <div class="text-center mb-6">
                  <h2 class="text-headline-small font-weight-bold mb-2">Create Account</h2>
                  <p class="text-body-medium text-medium-emphasis">
                    Complete your registration to get started
                  </p>
                </div>

                <!-- Loading State -->
                <div v-if="isValidatingToken" class="text-center py-8">
                  <v-progress-circular :size="50" :width="6" color="primary" indeterminate />
                  <p class="text-body-medium text-medium-emphasis mt-4">Validating invite...</p>
                </div>

                <!-- Invalid Token State -->
                <div v-else-if="tokenValidation && !tokenValidation.valid" class="text-center py-4">
                  <v-alert class="mb-4" type="error" variant="tonal">
                    <div class="d-flex align-center">
                      <v-icon start>mdi-alert-circle</v-icon>
                      <div>
                        <div class="font-weight-bold">Invalid Invite</div>
                        <div class="text-body-medium">{{ tokenValidation.error }}</div>
                      </div>
                    </div>
                  </v-alert>
                  <v-btn
                    color="primary"
                    variant="outlined"
                    prepend-icon="mdi-arrow-left"
                    @click="router.push('/login')"
                  >
                    Back to Login
                  </v-btn>
                </div>

                <!-- Registration Form -->
                <v-form
                  v-else-if="tokenValidation && tokenValidation.valid"
                  ref="formRef"
                  v-model="valid"
                  @submit.prevent="handleRegister"
                >
                  <!-- Role Info Card -->
                  <v-card :color="role?.color" class="mb-6" variant="tonal">
                    <v-card-text class="py-3">
                      <div class="d-flex align-center">
                        <v-icon :icon="role?.icon" :color="role?.color" class="me-3" />
                        <div>
                          <div class="text-title-small font-weight-bold">
                            You're registering as a {{ tokenValidation.role }}
                          </div>
                          <div class="text-body-small text-medium-emphasis">
                            {{ role?.description }}
                          </div>
                        </div>
                      </div>
                    </v-card-text>
                  </v-card>

                  <!-- Username Field -->
                  <v-text-field
                    v-model="formData.username"
                    label="Username"
                    prepend-inner-icon="mdi-account"
                    :disabled="isLoading"
                    :rules="[
                      rules.required('Username is required'),
                      rules.minLength(3, 'Username must be at least 3 characters'),
                    ]"
                    required
                    class="mb-4"
                    hint="Choose a unique username for your account"
                    persistent-hint
                  />

                  <!-- Email Field -->
                  <v-text-field
                    v-model="formData.email"
                    label="Email Address"
                    type="email"
                    prepend-inner-icon="mdi-email"
                    :disabled="isLoading"
                    :rules="[
                      rules.required('Email is required'),
                      rules.email('Please enter a valid email address'),
                    ]"
                    required
                    class="mb-4"
                    hint="This will be used for account recovery"
                    persistent-hint
                  />

                  <!-- Password Field -->
                  <v-text-field
                    v-model="formData.password"
                    label="Password"
                    :type="showPassword ? 'text' : 'password'"
                    prepend-inner-icon="mdi-lock"
                    :append-inner-icon="showPassword ? 'mdi-eye' : 'mdi-eye-off'"
                    :disabled="isLoading"
                    :rules="[
                      rules.required('Password is required'),
                      rules.minLength(8, 'Password must be at least 8 characters'),
                    ]"
                    required
                    class="mb-4"
                    hint="Choose a strong password with at least 8 characters"
                    persistent-hint
                    @click:append-inner="showPassword = !showPassword"
                  />

                  <!-- Confirm Password Field -->
                  <v-text-field
                    v-model="formData.confirmPassword"
                    label="Confirm Password"
                    :type="showConfirmPassword ? 'text' : 'password'"
                    prepend-inner-icon="mdi-lock-check"
                    :append-inner-icon="showConfirmPassword ? 'mdi-eye' : 'mdi-eye-off'"
                    :disabled="isLoading"
                    :rules="[rules.required('Please confirm your password'), confirmPasswordRule]"
                    required
                    class="mb-6"
                    @click:append-inner="showConfirmPassword = !showConfirmPassword"
                  />

                  <!-- Error Alert -->
                  <v-alert v-if="error" class="mb-4" type="error" variant="tonal">
                    {{ error }}
                  </v-alert>

                  <!-- Success Alert -->
                  <v-alert v-if="registrationSuccess" class="mb-4" type="success" variant="tonal">
                    <div class="font-weight-bold">Registration Successful!</div>
                    <div class="text-body-medium">
                      Your account has been created. Redirecting to login...
                    </div>
                  </v-alert>

                  <!-- Register Button -->
                  <v-btn
                    type="submit"
                    color="primary"
                    size="large"
                    block
                    :loading="isLoading"
                    :disabled="isLoading || !valid"
                    class="text-none mb-4"
                  >
                    <v-icon start>mdi-account-plus</v-icon>
                    {{ isLoading ? 'Creating Account...' : 'Create Account' }}
                  </v-btn>

                  <!-- Back to Login -->
                  <v-btn
                    color="primary"
                    variant="text"
                    size="small"
                    block
                    prepend-icon="mdi-arrow-left"
                    :disabled="isLoading"
                    @click="router.push('/login')"
                    class="text-none"
                  >
                    Back to Login
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useDarkMode } from '../composables/useDarkMode'
import { inviteService } from '../services/invite'
import { ROLE_OPTIONS } from '../constants/roles'

const router = useRouter()
const route = useRoute()
const { isDark } = useDarkMode()

const isLoading = ref(false)
const isValidatingToken = ref(true)
const error = ref(null)
const registrationSuccess = ref(false)
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const formRef = ref(null)
const valid = ref(false)
const tokenValidation = ref(null)

const formData = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const rules = {
  required:
    (message = 'This field is required') =>
    (v) =>
      !!v || message,
  email:
    (message = 'Please enter a valid email') =>
    (v) =>
      /.+@.+\..+/.test(v) || message,
  minLength: (min, message) => (v) => (v && v.length >= min) || message,
}

const confirmPasswordRule = (v) => v === formData.password || 'Passwords do not match'

const role = computed(() =>
  ROLE_OPTIONS.find((option) => option.value === tokenValidation.value?.role),
)

const validateInviteToken = async () => {
  const token = route.query.token

  if (!token) {
    tokenValidation.value = {
      valid: false,
      error: 'No invite token provided. Please use a valid invite link.',
    }
    isValidatingToken.value = false
    return
  }

  try {
    const validation = await inviteService.validateInvite(token)
    tokenValidation.value = validation
  } catch (err) {
    tokenValidation.value = {
      valid: false,
      error: err.response?.data?.detail || 'Failed to validate invite token',
    }
  } finally {
    isValidatingToken.value = false
  }
}

const handleRegister = async () => {
  const token = route.query.token

  if (!token) {
    error.value = 'No invite token found'
    return
  }
  if (!(await formRef.value.validate()).valid || isLoading.value) return

  try {
    error.value = null
    isLoading.value = true

    await inviteService.registerUserWithInvite({
      username: formData.username,
      email: formData.email,
      password: formData.password,
      token: token,
    })

    registrationSuccess.value = true

    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to create account. Please try again.'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  validateInviteToken()
})
</script>
