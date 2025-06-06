<!-- eslint-disable vue/multi-word-component-names -->
<template>
  <v-navigation-drawer
    v-model="drawer"
    :width="256"
    permanent
    class="owlculus-sidebar border-e"
  >
    <!-- Logo Section -->
    <v-container class="pa-4">
      <div class="d-flex justify-center align-center" style="height: 120px;">
        <v-img
          :src="isDark ? '/owl_logo_white.png' : '/owl_logo.png'"
          alt="Owlculus Logo"
          max-height="140"
          max-width="220"
          contain
        />
      </div>
    </v-container>

    <v-divider />

    <!-- Navigation Items -->
    <v-list nav density="comfortable" class="pt-4">
      <v-list-item
        v-for="item in navigationItems"
        :key="item.name"
        :to="item.href"
        :prepend-icon="item.icon"
        :title="item.name"
        :active="isCurrentRoute(item.href)"
        color="primary"
        rounded="xl"
        class="ma-1"
      />
    </v-list>

    <!-- Actions Section -->
    <template #append>
      <v-divider />
      <v-container class="pa-2">
        <v-btn
          :prepend-icon="isDark ? 'mdi-white-balance-sunny' : 'mdi-moon-waning-crescent'"
          :text="isDark ? 'Light Mode' : 'Dark Mode'"
          variant="text"
          block
          class="mb-2 justify-start"
          @click="toggleDark"
        />

        <v-btn
          prepend-icon="mdi-logout"
          text="Logout"
          color="error"
          variant="text"
          block
          class="justify-start"
          @click="handleLogout"
        />
      </v-container>
    </template>
  </v-navigation-drawer>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDarkMode } from '@/composables/useDarkMode'

const drawer = ref(true)
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isDark, toggleDark } = useDarkMode()

const navigationItems = computed(() => {
  // Don't show any items until auth is initialized
  if (!authStore.isInitialized) {
    return [];
  }

  const items = [
    { name: 'Cases', href: '/cases', icon: 'mdi-folder-outline' },
    { name: 'Plugins', href: '/plugins', icon: 'mdi-wrench-outline' },
  ]

  // Add settings for non-admin users
  if (!authStore.requiresAdmin()) {
    items.push({ name: 'Settings', href: '/settings', icon: 'mdi-cog-outline' })
  }

  // Only show clients and admin sections for admin users
  if (authStore.requiresAdmin()) {
    items.push(
      { name: 'Clients', href: '/clients', icon: 'mdi-account-group-outline' },
      { name: 'Admin', href: '/admin', icon: 'mdi-shield-account-outline' }
    )
  }

  return items
})

const isCurrentRoute = (path) => {
  return route.path === path
}

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
/* Styles handled by Vuetify border-e class */
</style>
