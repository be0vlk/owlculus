<template>
  <BaseDashboard compact :loading="loading" title="Admin">
    <template #header>
      <header class="d-flex flex-wrap align-center ga-4 mb-6">
        <div class="d-flex align-center ga-3">
          <v-icon icon="mdi-shield-account-outline" color="primary" size="28" />
          <div>
            <h1 class="text-headline-small font-weight-bold">Admin</h1>
            <p class="text-body-medium text-medium-emphasis mb-0">
              Manage workspace access and defaults
            </p>
          </div>
        </div>
        <v-spacer />
        <p class="text-body-medium text-medium-emphasis mb-0" aria-live="polite">
          <span>{{ userCount === null ? 'Users unavailable' : `${userCount} users` }}</span>
          <span aria-hidden="true" class="mx-3">·</span>
          <span>{{
            inviteCount === null ? 'Pending invites unavailable' : `${inviteCount} pending invites`
          }}</span>
        </p>
      </header>
    </template>

    <v-tabs v-model="activeTab" aria-label="Administration sections" show-arrows>
      <v-tab
        v-for="tab in tabs"
        :id="`admin-tab-${tab.value}`"
        :key="tab.value"
        :value="tab.value"
        :aria-controls="`admin-panel-${tab.value}`"
        >{{ tab.label }}</v-tab
      >
    </v-tabs>
    <v-divider />

    <div class="admin-workspace pt-6">
      <section
        v-for="tab in tabs"
        v-show="activeTab === tab.value"
        :id="`admin-panel-${tab.value}`"
        :key="tab.value"
        role="tabpanel"
        :aria-labelledby="`admin-tab-${tab.value}`"
        tabindex="0"
      >
        <template v-if="visited.has(tab.value)">
          <UserManagementCard
            v-if="tab.value === 'users'"
            embedded
            @count="userCount = $event"
            @invite="inviteUser"
            @confirmDelete="handleConfirmDelete"
            @notification="handleNotification"
          />
          <InviteManagementCard
            v-else-if="tab.value === 'invites'"
            ref="inviteCard"
            embedded
            @count="inviteCount = $event"
            @confirmDelete="handleConfirmDelete"
            @notification="handleNotification"
          />
          <ApiKeyManagementCard
            v-else-if="tab.value === 'keys'"
            embedded
            @confirmDelete="handleConfirmDelete"
            @notification="handleNotification"
          />
          <template v-else-if="tab.value === 'templates'">
            <v-tabs v-model="templateTab" aria-label="Template types" show-arrows class="mb-4">
              <v-tab
                id="template-tab-evidence"
                value="evidence"
                aria-controls="template-panel-evidence"
                >Evidence folders</v-tab
              >
              <v-tab id="template-tab-tasks" value="tasks" aria-controls="template-panel-tasks"
                >Task templates</v-tab
              >
            </v-tabs>
            <section
              id="template-panel-evidence"
              v-show="templateTab === 'evidence'"
              role="tabpanel"
              aria-labelledby="template-tab-evidence"
            >
              <EvidenceTemplateManagementCard embedded @notification="handleNotification" />
            </section>
            <section
              id="template-panel-tasks"
              v-show="templateTab === 'tasks'"
              role="tabpanel"
              aria-labelledby="template-tab-tasks"
            >
              <TaskTemplateManagementCard
                embedded
                @notification="handleNotification"
                @confirmDelete="handleConfirmDelete"
              />
            </section>
          </template>
          <SystemConfigurationCard
            v-else-if="tab.value === 'configuration'"
            embedded
            @notification="handleNotification"
          />
        </template>
      </section>
    </div>
  </BaseDashboard>

  <!-- Confirmation Dialog -->
  <ConfirmationDialog ref="confirmDialog" />

  <!-- Snackbar for notifications -->
  <v-snackbar
    v-model="snackbar.show"
    :color="snackbar.color"
    :timeout="snackbar.timeout"
    location="top right"
  >
    {{ snackbar.text }}
    <template #actions>
      <v-btn variant="text" @click="closeNotification"> Close </v-btn>
    </template>
  </v-snackbar>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotifications } from '@/composables/useNotifications'
import BaseDashboard from '@/components/BaseDashboard.vue'
import SystemConfigurationCard from '@/components/SystemConfigurationCard.vue'
import ApiKeyManagementCard from '@/components/ApiKeyManagementCard.vue'
import EvidenceTemplateManagementCard from '@/components/EvidenceTemplateManagementCard.vue'
import TaskTemplateManagementCard from '@/components/TaskTemplateManagementCard.vue'
import UserManagementCard from '@/components/UserManagementCard.vue'
import InviteManagementCard from '@/components/InviteManagementCard.vue'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'

const router = useRouter()
const authStore = useAuthStore()

// State
const loading = ref(true)
const route = useRoute()
const tabs = [
  { value: 'users', label: 'Users' },
  { value: 'invites', label: 'Invites' },
  { value: 'keys', label: 'API keys' },
  { value: 'templates', label: 'Templates' },
  { value: 'configuration', label: 'Case numbering' },
]
const activeTab = computed({
  get: () => (tabs.some((tab) => tab.value === route.query.tab) ? route.query.tab : 'users'),
  set: (tab) => router.replace({ query: { ...route.query, tab } }),
})
// Access lists also supply the summary. Other workspaces initialize on first visit.
const visited = ref(new Set(['users', 'invites']))
watch(activeTab, (tab) => visited.value.add(tab), { immediate: true })
const templateTab = ref('evidence')
const userCount = ref(null)
const inviteCount = ref(null)
const inviteCard = ref([])
const inviteUser = async () => {
  await router.replace({ query: { ...route.query, tab: 'invites' } })
  await nextTick()
  inviteCard.value[0]?.openCreateDialog()
}

// Notifications
const { snackbar, showNotification, closeNotification } = useNotifications()

// Confirmation dialog reference
const confirmDialog = ref(null)

// Event handlers
const handleNotification = ({ text, color }) => {
  showNotification(text, color)
}

const handleConfirmDelete = async ({ title, message, warning, onConfirm }) => {
  try {
    await confirmDialog.value.confirm({
      title,
      message,
      warning,
      confirmText: 'Delete',
      confirmColor: 'error',
      icon: 'mdi-delete-alert',
      iconColor: 'error',
    })

    // Execute the confirmation action
    await onConfirm()
  } catch {
    // User cancelled or action failed
  }
}

onMounted(async () => {
  if (!authStore.isAuthenticated || authStore.user?.role !== 'Admin') {
    router.push('/')
    return
  }

  // Let child components handle their own loading
  loading.value = false
})
</script>

<style scoped>
.admin-workspace {
  min-width: 0;
}
.admin-workspace :deep(.v-card-title) {
  white-space: normal;
}
.admin-workspace :deep(.admin-dashboard-table) {
  max-width: 100%;
}
</style>
