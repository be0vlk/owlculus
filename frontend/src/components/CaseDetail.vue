<template>
  <div>
    <v-row>
      <v-col cols="12" md="6">
        <div class="mb-4">
          <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
            Title
          </v-list-item-subtitle>
          <v-list-item-title class="text-body-1">
            {{ caseData?.title || 'N/A' }}
          </v-list-item-title>
        </div>
      </v-col>
      <v-col cols="12" md="6">
        <div class="mb-4">
          <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
            Status
          </v-list-item-subtitle>
          <v-chip :color="getStatusColor(caseData?.status)" size="small" variant="tonal">
            {{ caseData?.status || 'N/A' }}
          </v-chip>
        </div>
      </v-col>
      <v-col cols="12" md="6">
        <div class="mb-4">
          <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
            Client
          </v-list-item-subtitle>
          <v-list-item-title class="text-body-1">
            {{ client?.name || 'No client assigned' }}
          </v-list-item-title>
        </div>
      </v-col>
      <v-col cols="12" md="6">
        <div class="mb-4">
          <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
            Created Date
          </v-list-item-subtitle>
          <v-list-item-title class="text-body-1">
            {{ formatDate(caseData?.created_at) || 'N/A' }}
          </v-list-item-title>
        </div>
      </v-col>
      <v-col cols="12">
        <div class="mb-4">
          <v-list-item-subtitle class="text-subtitle-2 font-weight-medium mb-1">
            Assigned Users
          </v-list-item-subtitle>
          <div v-if="caseData?.users?.length" class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="user in caseData.users"
              :key="user.id"
              size="small"
              color="grey-lighten-1"
              variant="tonal"
            >
              {{ user.username }}
            </v-chip>
          </div>
          <v-list-item-title v-else class="text-body-1 text-medium-emphasis">
            No users assigned
          </v-list-item-title>
        </div>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { formatDate } from '../composables/dateUtils'

defineProps({
  caseData: { type: Object, required: true },
  client: { type: Object, default: () => ({}) },
})

// Function to get status color - consistent with case dashboard table
const getStatusColor = (status) => {
  return status === 'Open' ? 'success' : 'default'
}
</script>
