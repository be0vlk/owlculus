<template>
  <BaseDashboard title="Cases">
    <v-alert v-if="error" type="error" variant="tonal" class="mb-6" role="alert">
      {{ error }}
    </v-alert>

    <v-card variant="outlined">
      <v-card-title class="d-flex flex-wrap align-center ga-3 pa-4 bg-surface">
        <v-icon class="me-3" color="primary" icon="mdi-briefcase" size="large" />
        <div class="flex-grow-1">
          <div class="text-title-large font-weight-bold">Case Management</div>
          <div class="text-body-medium text-medium-emphasis">
            Manage investigations and assignments
          </div>
        </div>
        <div class="d-flex align-center ga-2">
          <v-btn
            size="small"
            v-if="authStore.requiresAdmin()"
            color="primary"
            prepend-icon="mdi-plus"
            @click="isNewCaseModalOpen = true"
          >
            New Case
          </v-btn>
          <v-tooltip location="bottom" text="Refresh case list">
            <template #activator="{ props }">
              <v-btn
                size="small"
                aria-label="Refresh case list"
                :loading="loading"
                icon="mdi-refresh"
                v-bind="props"
                variant="outlined"
                @click="loadData"
              />
            </template>
          </v-tooltip>
        </div>
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-4">
        <v-row class="mb-0 align-center">
          <v-col cols="12" md="8">
            <div class="d-flex align-center ga-2 flex-wrap">
              <span class="text-body-medium font-weight-medium me-2">Filter:</span>
              <v-chip-group
                v-model="activeQuickFilter"
                color="primary"
                selected-class="text-primary"
                variant="outlined"
              >
                <v-chip filter size="small" value="all"> All Cases </v-chip>
                <v-chip filter size="small" value="my-cases"> My Cases </v-chip>
                <v-chip filter size="small" value="unassigned"> Unassigned </v-chip>
              </v-chip-group>
            </div>
          </v-col>

          <v-col cols="12" md="4">
            <div class="d-flex align-center ga-2 justify-end flex-wrap">
              <div class="d-flex align-center flex-shrink-0">
                <v-switch
                  v-model="showClosedCases"
                  class="me-2"
                  color="primary"
                  density="comfortable"
                  hide-details
                />
                <span class="text-body-medium text-no-wrap">Show Closed</span>
              </div>

              <v-text-field
                v-model="searchQuery"
                class="flex-grow-1"
                clearable
                hide-details
                label="Search cases..."
                prepend-inner-icon="mdi-magnify"
                style="min-width: 200px; max-width: 280px"
              />
            </div>
          </v-col>
        </v-row>
      </v-card-text>

      <v-divider />

      <v-data-table
        :headers="headers"
        :items="filteredCases"
        :sort-by="[{ key: 'created_at', order: 'desc' }]"
        :loading="loading"
        class="elevation-0 case-dashboard-table"
        :hide-no-data="!!error"
        hover
        item-key="id"
        @click:row="handleRowClick"
      >
        <template #[`item.status`]="{ item }">
          <v-chip
            :color="item.status === 'Open' ? 'success' : 'default'"
            size="small"
            variant="tonal"
          >
            {{ item.status }}
          </v-chip>
        </template>

        <template #[`item.users`]="{ item }">
          <div v-if="item.users?.length" class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="user in item.users"
              :key="user.id"
              :color="user.is_lead ? 'primary' : 'grey-lighten-1'"
              size="small"
              variant="tonal"
            >
              <v-icon v-if="user.is_lead" size="x-small" start>mdi-star</v-icon>
              {{ user.username }}
            </v-chip>
          </div>
          <v-chip v-else color="grey" size="small" variant="outlined"> Unassigned </v-chip>
        </template>

        <template #[`item.client_id`]="{ item }">
          {{ getClientName(item.client_id) }}
        </template>

        <template #[`item.created_at`]="{ item }">
          <span class="text-body-medium">
            {{ formatDate(item.created_at) }}
          </span>
        </template>

        <template #no-data>
          <div class="text-center pa-12">
            <v-icon class="mb-4" color="grey-lighten-1" icon="mdi-folder-open-outline" size="64" />
            <h3 class="text-title-large font-weight-medium mb-2">{{ emptyState.title }}</h3>
            <p class="text-body-medium text-medium-emphasis mb-4">{{ emptyState.message }}</p>
            <v-btn
              v-if="emptyState.create"
              color="primary"
              prepend-icon="mdi-plus"
              @click="isNewCaseModalOpen = true"
            >
              Create First Case
            </v-btn>
          </div>
        </template>
      </v-data-table>
    </v-card>
  </BaseDashboard>

  <NewCaseModal
    :is-open="isNewCaseModalOpen"
    @close="isNewCaseModalOpen = false"
    @created="handleCaseCreated"
  />

  <v-snackbar
    v-model="snackbar.show"
    :color="snackbar.color"
    :timeout="snackbar.timeout"
    location="top right"
    :role="snackbar.color === 'error' ? 'alert' : 'status'"
  >
    {{ snackbar.text }}
    <template #actions>
      <v-btn variant="text" @click="closeNotification"> Close </v-btn>
    </template>
  </v-snackbar>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import BaseDashboard from '../components/BaseDashboard.vue'
import NewCaseModal from '../components/NewCaseModal.vue'
import { formatDate } from '../composables/dateUtils'
import { useNotifications } from '../composables/useNotifications'
import { useRoute, useRouter } from 'vue-router'
import { useActiveCaseStore } from '../stores/activeCase'
import { useAuthStore } from '../stores/auth'
import { useClientsStore } from '../stores/clients'

const route = useRoute()
const router = useRouter()
const activeCase = useActiveCaseStore()
const authStore = useAuthStore()
const clientsStore = useClientsStore()
const { snackbar, showNotification, closeNotification } = useNotifications()

const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')
const showClosedCases = ref(false)
const activeQuickFilter = ref('all')
const isNewCaseModalOpen = ref(false)

watch(
  () => route.query.create,
  (create) => {
    if (create !== '1' || !authStore.requiresAdmin()) return
    isNewCaseModalOpen.value = true
    const query = { ...route.query }
    delete query.create
    router.replace({ query })
  },
  { immediate: true },
)

const headers = [
  { title: 'Case Number', key: 'case_number' },
  { title: 'Title', key: 'title' },
  { title: 'Client', key: 'client_id' },
  { title: 'Status', key: 'status' },
  { title: 'Created', key: 'created_at' },
  { title: 'Assigned Users', key: 'users', sortable: false },
]

const clientNames = computed(() =>
  Object.fromEntries(clientsStore.clients.map((client) => [client.id, client.name])),
)
const getClientName = (clientId) => clientNames.value[clientId] || 'Unknown Client'

const filteredCases = computed(() => {
  const query = searchQuery.value?.toLowerCase()
  const userId = authStore.user?.id
  return activeCase.accessibleCases.filter((item) => {
    if (!showClosedCases.value && item.status !== 'Open') return false
    if (activeQuickFilter.value === 'my-cases' && userId) {
      if (!item.users?.some((user) => user.id === userId)) return false
    }
    if (activeQuickFilter.value === 'unassigned' && item.users?.length) return false
    if (!query) return true
    return (
      [item.case_number, item.title, getClientName(item.client_id), item.status].some((value) =>
        (value || '').toLowerCase().includes(query),
      ) || !!item.users?.some((user) => (user.username || '').toLowerCase().includes(query))
    )
  })
})

const emptyState = computed(() => {
  if (searchQuery.value) {
    return {
      title: 'No results found',
      message: 'Try adjusting your search terms or removing filters to see more results.',
    }
  }
  if (activeQuickFilter.value === 'my-cases') {
    return {
      title: 'No cases assigned to you',
      message: "You haven't been assigned to any cases yet. Check with your administrator.",
    }
  }
  if (activeQuickFilter.value === 'unassigned') {
    return {
      title: 'No unassigned cases',
      message: 'All cases have been assigned to team members.',
    }
  }
  if (!activeCase.accessibleCases.length) {
    return authStore.requiresAdmin()
      ? {
          title: 'No cases yet',
          message: 'Get started by creating your first investigation case.',
          create: true,
        }
      : { title: 'No cases yet', message: 'Contact an administrator to be assigned to a case.' }
  }
  return {
    title: 'No cases match your filters',
    message: 'Try adjusting your filters to see more cases.',
  }
})

const loadData = async () => {
  try {
    loading.value = true
    error.value = null
    await activeCase.refresh()
    if (activeCase.error) throw new Error(activeCase.error)
    // Client names are optional; their failure does not block the case list.
    await clientsStore.refresh().catch((err) => console.error('Failed to load clients:', err))
  } catch (err) {
    error.value = 'Failed to load dashboard data'
    console.error('Dashboard loading error:', err)
  } finally {
    loading.value = false
  }
}

const handleCaseCreated = async (newCase, { assignmentWarning } = {}) => {
  await loadData()
  isNewCaseModalOpen.value = false
  if (assignmentWarning) {
    showNotification(
      `Case "${newCase?.case_number || 'New case'}" was created, but ${assignmentWarning}. Manage the case users to retry.`,
      'warning',
    )
  } else {
    showNotification(`Case "${newCase?.case_number || 'New case'}" created successfully`)
  }
  activeCase.notification = snackbar.value.text
  await activeCase.select(newCase.id, { overview: true })
}

const handleRowClick = (event, { item }) => {
  activeCase.select(item.id, { overview: true })
}

onMounted(loadData)
</script>
