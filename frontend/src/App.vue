<template>
  <v-app>
    <router-view />
    
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
import { onMounted, onUnmounted, ref } from 'vue'
import { useDarkMode } from '@/composables/useDarkMode'

// Initialize dark mode
useDarkMode()

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
/* Global styles */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: Roboto, -apple-system, BlinkMacSystemFont, 'Segoe UI', Oxygen,
    Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>