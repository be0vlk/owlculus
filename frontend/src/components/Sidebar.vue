<!-- eslint-disable vue/multi-word-component-names -->
<template>
  <v-navigation-drawer
    v-model="drawer"
    :width="256"
    :rail="smAndDown"
    :rail-width="56"
    class="owlculus-sidebar border-e"
    permanent
  >
    <!-- Logo Section -->
    <v-container :class="smAndDown ? 'pa-1' : 'pa-4'">
      <div
        class="d-flex justify-center align-center"
        :style="{ height: smAndDown ? '48px' : '120px' }"
      >
        <v-img
          :src="isDark ? '/owl_logo_white.png' : '/owl_logo.png'"
          alt="Owlculus Logo"
          max-height="140"
          max-width="220"
        />
      </div>
    </v-container>

    <ActiveCaseSwitcher v-if="!smAndDown" />
    <v-divider />

    <!-- Navigation Items -->
    <v-list nav density="comfortable" class="pt-4">
      <v-list-item
        v-for="item in navigationItems"
        :key="item.name"
        :to="item.disabled ? undefined : item.href"
        :disabled="item.disabled"
        :aria-disabled="item.disabled || undefined"
        :prepend-icon="item.icon"
        :aria-label="item.disabled ? `${item.name}: ${caseNavigationExplanation}` : item.name"
        color="primary"
        rounded="xl"
        class="ma-1"
        min-height="56"
      >
        <template #title>
          <span class="sidebar-item-title">{{ item.name }}</span>
        </template>
      </v-list-item>
    </v-list>

    <!-- Actions Section -->
    <template #append>
      <v-divider />
      <v-container class="pa-2">
        <v-btn
          :prepend-icon="isDark ? 'mdi-white-balance-sunny' : 'mdi-moon-waning-crescent'"
          :text="smAndDown ? undefined : isDark ? 'Light Mode' : 'Dark Mode'"
          :aria-label="isDark ? 'Light Mode' : 'Dark Mode'"
          :icon="
            smAndDown
              ? isDark
                ? 'mdi-white-balance-sunny'
                : 'mdi-moon-waning-crescent'
              : undefined
          "
          variant="text"
          :block="!smAndDown"
          size="default"
          :class="smAndDown ? 'mb-2' : 'mb-2 justify-start'"
          @click="toggleDark"
        />

        <v-btn
          prepend-icon="mdi-logout"
          :text="smAndDown ? undefined : 'Logout'"
          aria-label="Logout"
          :icon="smAndDown ? 'mdi-logout' : undefined"
          color="error"
          variant="text"
          :block="!smAndDown"
          size="default"
          :class="smAndDown ? undefined : 'justify-start'"
          @click="handleLogout"
        />
      </v-container>
    </template>
  </v-navigation-drawer>
  <v-app-bar v-if="smAndDown" height="112">
    <ActiveCaseSwitcher />
  </v-app-bar>
</template>

<script setup>
import { useDisplay } from 'vuetify'
import ActiveCaseSwitcher from './ActiveCaseSwitcher.vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDarkMode } from '@/composables/useDarkMode'

const { smAndDown } = useDisplay()
const drawer = ref(true)
const router = useRouter()
const authStore = useAuthStore()
const activeCase = useActiveCaseStore()
const caseNavigationExplanation = computed(() =>
  activeCase.loading || !activeCase.ready
    ? 'Cases are still being resolved.'
    : 'No accessible case. Create a case or contact an administrator.',
)
const { isDark, toggleDark } = useDarkMode()

const navigationItems = computed(() => {
  // Don't show any items until auth is initialized
  if (!authStore.isInitialized) {
    return []
  }

  const items = [
    { name: 'Cases', href: '/cases', icon: 'mdi-folder-outline' },
    {
      name: 'Case overview',
      href: `/case/${activeCase.activeCaseId}`,
      icon: 'mdi-briefcase-outline',
    },
  ]

  // Add Clients for admin users
  if (authStore.requiresAdmin()) {
    items.push({ name: 'Clients', href: '/clients', icon: 'mdi-account-group-outline' })
  }

  items.push(
    {
      name: 'Tasks',
      href: activeCase.activeCaseId ? `/case/${activeCase.activeCaseId}/tasks` : '/tasks',
      icon: 'mdi-checkbox-marked-circle-outline',
    },
    { name: 'Plugins', href: '/plugins', icon: 'mdi-wrench-outline' },
  )

  // Add Hunts for non-analyst users
  if (authStore.user?.role !== 'Analyst') {
    items.push({ name: 'Hunts', href: '/hunts', icon: 'mdi-target' })
  }

  items.push({ name: 'Strixy (WIP)', href: '/strixy', icon: 'mdi-robot' })

  // Add Admin settings for admin users
  if (authStore.requiresAdmin()) {
    items.push({ name: 'Admin', href: '/admin', icon: 'mdi-shield-account-outline' })
  } else {
    // Add regular settings for non-admin users
    items.push({ name: 'Settings', href: '/settings', icon: 'mdi-cog-outline' })
  }

  return items.map((item) => ({
    ...item,
    disabled: router.resolve(item.href).meta.requiresActiveCase && !activeCase.activeCaseId,
  }))
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
/* Fix text clipping in navigation items and increase font size */
.sidebar-item-title {
  display: block;
  line-height: 1.2;
  padding-bottom: 2px;
  font-size: medium;
  font-weight: 500;
}
</style>
