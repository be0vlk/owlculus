<template>
  <v-app>
    <Sidebar />
    
    <v-main>
      <v-container class="pa-6">
        <!-- Page Header -->
        <div class="mb-6">
          <v-row align="center" justify="space-between">
            <v-col>
              <h1 class="text-h4 font-weight-bold">
                Case Dashboard
              </h1>
            </v-col>
            <v-col cols="auto">
              <v-btn
                v-if="authStore.requiresAdmin()"
                color="primary"
                prepend-icon="mdi-plus"
                @click="isNewCaseModalOpen = true"
              >
                New Case
              </v-btn>
            </v-col>
          </v-row>
        </div>

        <!-- Loading state -->
        <v-card v-if="loading">
          <v-card-title class="d-flex align-center justify-space-between pa-6">
            <div class="d-flex ga-2">
              <v-skeleton-loader type="button" width="80" />
              <v-skeleton-loader type="button" width="90" />
              <v-skeleton-loader type="button" width="100" />
            </div>
            <div class="d-flex align-center ga-4">
              <v-skeleton-loader type="button" width="150" />
              <v-skeleton-loader type="text" width="300" />
            </div>
          </v-card-title>
          <v-skeleton-loader 
            type="table" 
            class="ma-4"
          />
        </v-card>

        <!-- Error state -->
        <v-alert
          v-else-if="error"
          type="error"
          class="ma-4"
          :text="error"
          prominent
          border="start"
        />

        <!-- Cases data table -->
        <v-card v-else>
          <!-- Filters and Search Toolbar -->
          <v-card-title class="d-flex align-center justify-space-between">
            <!-- Quick Filter Chips -->
            <div class="d-flex align-center ga-2">
              <v-chip-group
                v-model="activeQuickFilter"
                selected-class="text-primary"
                color="primary"
                variant="outlined"
              >
                <v-chip
                  filter
                  value="all"
                  size="small"
                >
                  All Cases
                </v-chip>
                <v-chip
                  filter
                  value="my-cases"
                  size="small"
                >
                  My Cases
                </v-chip>
                <v-chip
                  filter
                  value="unassigned"
                  size="small"
                >
                  Unassigned
                </v-chip>
              </v-chip-group>
            </div>
            
            <!-- Controls -->
            <div class="d-flex align-center ga-4">
              <!-- Show Closed Cases Switch -->
              <v-switch
                v-model="showClosedCases"
                label="Show Closed Cases"
                color="primary"
                hide-details
              />
              
              <!-- Search Field -->
              <v-text-field
                v-model="searchQuery"
                prepend-inner-icon="mdi-magnify"
                label="Search cases..."
                variant="outlined"
                density="compact"
                hide-details
                style="min-width: 300px;"
              />
            </div>
          </v-card-title>

            <v-data-table
              :headers="vuetifyHeaders"
              :items="enhancedFilteredCases"
              :loading="loading"
              item-key="id"
              class="elevation-0 case-dashboard-table"
              hover
              @click:row="handleRowClick"
            >
              <!-- Status chip -->
              <template #[`item.status`]="{ item }">
                <v-chip
                  :color="item.status === 'Open' ? 'success' : 'default'"
                  size="small"
                  variant="tonal"
                >
                  {{ item.status }}
                </v-chip>
              </template>

              <!-- Users column -->
              <template #[`item.users`]="{ item }">
                <div v-if="item.users?.length" class="d-flex flex-wrap ga-1">
                  <v-chip 
                    v-for="user in item.users" 
                    :key="user.id"
                    :color="getUserRoleColor(user.role)"
                    size="small"
                    variant="tonal"
                  >
                    {{ user.username }}
                  </v-chip>
                </div>
                <v-chip
                  v-else
                  size="small"
                  variant="outlined"
                  color="grey"
                >
                  Unassigned
                </v-chip>
              </template>

              <!-- Client name -->
              <template #[`item.client_id`]="{ item }">
                {{ getClientName(item.client_id) }}
              </template>

              <!-- Created date -->
              <template #[`item.created_at`]="{ item }">
                <span class="text-body-2">
                  {{ formatDate(item.created_at) }}
                </span>
              </template>

              <!-- Empty state -->
              <template #no-data>
                <div class="text-center pa-12">
                  <v-icon
                    icon="mdi-folder-open-outline"
                    size="64"
                    color="grey-lighten-1"
                    class="mb-4"
                  />
                  <h3 class="text-h6 font-weight-medium mb-2">
                    {{ getEmptyStateTitle() }}
                  </h3>
                  <p class="text-body-2 text-medium-emphasis mb-4">
                    {{ getEmptyStateMessage() }}
                  </p>
                  <v-btn
                    v-if="shouldShowCreateButton()"
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
      </v-container>
    </v-main>
    
    <NewCaseModal 
      :is-open="isNewCaseModalOpen" 
      @close="isNewCaseModalOpen = false" 
      @created="handleCaseCreated" 
    />
  </v-app>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import Sidebar from '../components/Sidebar.vue'
import NewCaseModal from '../components/NewCaseModal.vue'
import { useDashboard } from '../composables/useDashboard'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const {
  loading,
  error,
  searchQuery,
  showClosedCases,
  loadData,
  getClientName,
  formatDate,
  sortedAndFilteredCases,
  cases
} = useDashboard()

const isNewCaseModalOpen = ref(false)
const activeQuickFilter = ref('all')

// Convert the original columns to Vuetify data table headers
const vuetifyHeaders = computed(() => [
  { title: 'Case Number', value: 'case_number', sortable: true },
  { title: 'Title', value: 'title', sortable: true },
  { title: 'Client', value: 'client_id', sortable: true },
  { title: 'Status', value: 'status', sortable: true },
  { title: 'Created', value: 'created_at', sortable: true },
  { title: 'Assigned Users', value: 'users', sortable: false },
])

// Enhanced filtered cases with quick filter support
const enhancedFilteredCases = computed(() => {
  let filteredCases = sortedAndFilteredCases.value

  // Apply quick filter
  if (activeQuickFilter.value === 'my-cases' && authStore.user) {
    filteredCases = filteredCases.filter(case_ => 
      case_.users?.some(user => user.id === authStore.user.id)
    )
  } else if (activeQuickFilter.value === 'unassigned') {
    filteredCases = filteredCases.filter(case_ => 
      !case_.users || case_.users.length === 0
    )
  }

  return filteredCases
})

const handleCaseCreated = () => {
  // Refresh the cases list
  loadData()
  isNewCaseModalOpen.value = false
}

const handleRowClick = (event, { item }) => {
  router.push(`/case/${item.id}`)
}

// Function to get color for user role chips
const getUserRoleColor = () => {
  // Return light grey for all user chips
  return 'grey-lighten-1'
}


// Empty state functions
const getEmptyStateTitle = () => {
  if (searchQuery.value) {
    return 'No results found'
  } else if (activeQuickFilter.value === 'my-cases') {
    return 'No cases assigned to you'
  } else if (activeQuickFilter.value === 'unassigned') {
    return 'No unassigned cases'
  } else if ((cases.value || []).length === 0) {
    return 'No cases yet'
  } else {
    return 'No cases match your filters'
  }
}

const getEmptyStateMessage = () => {
  if (searchQuery.value) {
    return 'Try adjusting your search terms or removing filters to see more results.'
  } else if (activeQuickFilter.value === 'my-cases') {
    return 'You haven\'t been assigned to any cases yet. Check with your administrator.'
  } else if (activeQuickFilter.value === 'unassigned') {
    return 'All cases have been assigned to team members.'
  } else if ((cases.value || []).length === 0) {
    return 'Get started by creating your first investigation case.'
  } else {
    return 'Try adjusting your filters to see more cases.'
  }
}

const shouldShowCreateButton = () => {
  return (cases.value || []).length === 0 && !searchQuery.value && activeQuickFilter.value === 'all' && authStore.requiresAdmin()
}

onMounted(loadData)
</script>

<style scoped>
.case-dashboard-table :deep(.v-data-table__tr:hover) {
  background-color: rgba(var(--v-theme-primary), 0.04) !important;
  cursor: pointer;
}

.case-dashboard-table :deep(.v-data-table__td) {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08) !important;
}

.case-dashboard-table :deep(.v-data-table__th) {
  padding: 16px !important;
  font-weight: 600 !important;
  color: rgba(var(--v-theme-on-surface), 0.87) !important;
  border-bottom: 2px solid rgba(var(--v-theme-on-surface), 0.12) !important;
}

.case-dashboard-table :deep(.v-data-table-rows-no-data) {
  padding: 48px 16px !important;
}
</style>
