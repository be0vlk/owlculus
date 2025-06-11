<template>
  <div>
    <Sidebar v-if="showSidebar" />

    <v-main>
      <v-container fluid class="pa-6">
        <!-- Page Header Card -->
        <v-card class="mb-6 header-gradient">
          <v-card-title class="d-flex align-center pa-6 text-white">
            <div class="text-h4 font-weight-bold">{{ title }}</div>
            <v-spacer />
            <slot name="header-actions" />
          </v-card-title>
        </v-card>

        <!-- Loading State -->
        <slot name="loading" v-if="loading">
          <v-card variant="outlined">
            <v-card-title class="d-flex align-center pa-4 bg-surface">
              <v-skeleton-loader type="text" width="200" />
              <v-spacer />
              <v-skeleton-loader type="button" width="120" />
              <v-skeleton-loader type="text" width="200" class="ml-2" />
            </v-card-title>
            <v-divider />
            <v-skeleton-loader
              type="table"
              class="pa-4"
            />
          </v-card>
        </slot>

        <!-- Error State -->
        <slot name="error" v-else-if="error">
          <v-alert
            type="error"
            variant="tonal"
            border="start"
            prominent
            icon="mdi-alert-circle"
            class="mb-6"
          >
            <v-alert-title>Error Loading {{ title }}</v-alert-title>
            {{ error }}
          </v-alert>
        </slot>

        <!-- Main Content -->
        <slot v-else />
      </v-container>
    </v-main>
  </div>
</template>

<script setup>
import Sidebar from './Sidebar.vue'

defineProps({
  title: {
    type: String,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: null
  },
  showSidebar: {
    type: Boolean,
    default: true
  }
})
</script>

<style scoped>
.header-gradient {
  background: linear-gradient(
    135deg,
    rgb(var(--v-theme-primary)) 0%,
    rgb(var(--v-theme-primary), 0.8) 100%
  ) !important;
}
</style>