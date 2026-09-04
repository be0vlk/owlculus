<template>
  <v-app>
    <FullPageLoading v-if="!authStore.isInitialized" />
    <BaseDashboard
      v-else-if="caseContextBlocked"
      :title="routeCaseId(route) ? 'Case Details' : 'Cases'"
      :loading="!activeCase.error"
      :error="activeCase.error"
    />
    <router-view v-else :key="workspaceKey" />

    <v-snackbar
      :model-value="!!activeCase.notification"
      :timeout="-1"
      role="status"
      location="top center"
    >
      {{ activeCase.notification }}
      <template #actions>
        <v-btn variant="text" @click="activeCase.notification = ''">Dismiss</v-btn>
      </template>
    </v-snackbar>

    <!-- Global session expiration notification -->
    <v-snackbar
      v-model="sessionSnackbar.show"
      :color="sessionSnackbar.color"
      :timeout="sessionSnackbar.timeout"
      location="top center"
    >
      {{ sessionSnackbar.text }}
      <template #actions>
        <v-btn variant="text" @click="sessionSnackbar.show = false"> Close </v-btn>
      </template>
    </v-snackbar>
  </v-app>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import BaseDashboard from '@/components/BaseDashboard.vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import { routeCaseId } from '@/utils/caseNavigation'
import { useDarkMode } from '@/composables/useDarkMode'
import FullPageLoading from '@/components/FullPageLoading.vue'
import { useAuthStore } from '@/stores/auth'

// Initialize dark mode
useDarkMode()
const authStore = useAuthStore()
const activeCase = useActiveCaseStore()
const route = useRoute()
const workspaceKey = computed(() => (routeCaseId(route) ? `case-${routeCaseId(route)}` : undefined))
const caseContextBlocked = computed(
  () =>
    (authStore.isAuthenticated && !activeCase.initialized) ||
    (routeCaseId(route) &&
      (!activeCase.ready || String(activeCase.activeCaseId) !== String(routeCaseId(route)))),
)
authStore.init()

// Global session expiration notification
const sessionSnackbar = ref({
  show: false,
  text: '',
  color: 'error',
  timeout: 6000,
})

// Handle session expiration notification
const handleSessionExpired = (event) => {
  sessionSnackbar.value.text = event.detail.message
  sessionSnackbar.value.show = true
}

onMounted(() => {
  window.addEventListener('api:sessionExpired', handleSessionExpired)
})

onUnmounted(() => {
  window.removeEventListener('api:sessionExpired', handleSessionExpired)
})
</script>

<style>
body {
  font-family:
    Roboto,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    Oxygen,
    Ubuntu,
    Cantarell,
    'Open Sans',
    'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>
