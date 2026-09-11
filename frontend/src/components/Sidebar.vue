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

    <nav aria-label="Main navigation">
      <section v-for="section in navigationSections" :key="section.name" :aria-label="section.name">
        <h2 v-if="!smAndDown" class="sidebar-section-title">{{ section.name }}</h2>
        <v-divider v-else class="my-2" />
        <v-list nav density="comfortable">
          <v-list-item
            v-for="item in section.items"
            :key="item.name"
            :to="item.disabled ? undefined : item.href"
            :disabled="item.disabled"
            :aria-disabled="item.disabled || undefined"
            :prepend-icon="item.icon"
            :aria-label="item.disabled ? `${item.name}: ${caseNavigationExplanation}` : item.name"
            color="primary"
            rounded="xl"
            class="ma-1"
            min-height="46"
          >
            <template #title>
              <span class="sidebar-item-title">{{ item.name }}</span>
            </template>
          </v-list-item>
        </v-list>
      </section>
    </nav>

    <!-- Actions Section -->
    <template #append>
      <v-divider />
      <v-list v-if="settingsItem" nav density="compact" aria-label="Settings navigation">
        <v-list-item
          :to="settingsItem.href"
          :prepend-icon="settingsItem.icon"
          :aria-label="settingsItem.name"
          :title="settingsItem.name"
          color="primary"
          rounded="xl"
          class="ma-1"
          min-height="46"
        />
      </v-list>
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

const navigationSections = computed(() => {
  // Don't show any items until auth is initialized
  if (!authStore.isInitialized) {
    return []
  }

  const managementItems = [{ name: 'Cases', href: '/cases', icon: 'mdi-folder-outline' }]
  const items = [
    {
      name: 'Dashboard',
      href: `/case/${activeCase.activeCaseId}`,
      icon: 'mdi-briefcase-outline',
    },
  ]

  // Add management pages for admin users
  if (authStore.requiresAdmin()) {
    managementItems.push(
      { name: 'Admin', href: '/admin', icon: 'mdi-shield-account-outline' },
      { name: 'Clients', href: '/clients', icon: 'mdi-account-group-outline' },
    )
  }

  items.push(
    {
      name: 'Tasks',
      href: activeCase.activeCaseId ? `/case/${activeCase.activeCaseId}/tasks` : '/tasks',
      icon: 'mdi-checkbox-marked-circle-outline',
    },
    {
      name: 'Plugins',
      href: activeCase.activeCaseId ? `/case/${activeCase.activeCaseId}/plugins` : '/plugins',
      icon: 'mdi-wrench-outline',
    },
  )

  // Add Hunts for non-analyst users
  if (authStore.user?.role !== 'Analyst') {
    items.push({
      name: 'Hunts',
      href: activeCase.activeCaseId ? `/case/${activeCase.activeCaseId}/hunts` : '/hunts',
      icon: 'mdi-target',
    })
  }

  items.push({
    name: 'Strixy (WIP)',
    href: activeCase.activeCaseId ? `/case/${activeCase.activeCaseId}/strixy` : '/strixy',
    icon: 'mdi-robot',
  })

  return [
    { name: 'Case work', items },
    { name: 'Management', items: managementItems },
  ].map((section) => ({
    ...section,
    items: section.items
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((item) => ({
        ...item,
        disabled: router.resolve(item.href).meta.requiresActiveCase && !activeCase.activeCaseId,
      })),
  }))
})

const settingsItem = computed(() => {
  if (!authStore.isInitialized || authStore.requiresAdmin()) return null
  return { name: 'Settings', href: '/settings', icon: 'mdi-cog-outline' }
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.sidebar-section-title {
  padding: 20px 20px 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  opacity: 0.65;
}

/* Fix text clipping in navigation items and increase font size */
.sidebar-item-title {
  display: block;
  line-height: 1.2;
  padding-bottom: 2px;
  font-size: medium;
  font-weight: 500;
}
</style>
