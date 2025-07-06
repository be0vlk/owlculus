<template>
  <v-card class="hunt-card" elevation="1" hover rounded="lg" @click="$emit('view-details', hunt)">
    <!-- Hunt Category Header -->
    <v-card-title class="d-flex align-center pa-3 header-gradient text-white">
      <v-icon :icon="categoryIcon" color="white" size="small" class="me-2" />
      <span class="text-caption text-uppercase font-weight-bold">{{ displayCategory }}</span>
      <v-spacer />
      <v-chip :color="hunt.is_active ? 'success' : 'error'" size="x-small" variant="flat">
        {{ hunt.is_active ? 'Active' : 'Inactive' }}
      </v-chip>
    </v-card-title>

    <v-divider />

    <!-- Hunt Details -->
    <v-card-text class="pa-4">
      <div class="text-h6 font-weight-bold mb-2">{{ hunt.display_name }}</div>
      <div class="text-body-2 text-medium-emphasis mb-3 hunt-description">
        {{ hunt.description }}
      </div>

      <!-- Hunt Stats -->
      <div class="d-flex align-center justify-space-between mb-3">
        <div class="d-flex align-center">
          <v-icon icon="mdi-play-box-multiple" size="small" class="me-1" />
          <span class="text-caption">{{ hunt.step_count || 0 }} steps</span>
        </div>
        <div class="d-flex align-center">
          <v-icon icon="mdi-clock-outline" size="small" class="me-1" />
          <span class="text-caption">v{{ hunt.version }}</span>
        </div>
      </div>
    </v-card-text>

    <!-- Actions -->
    <v-card-actions class="pa-3 pt-0">
      <v-btn
        color="primary"
        variant="elevated"
        size="small"
        @click.stop="$emit('execute', hunt)"
        :disabled="!hunt.is_active"
        block
      >
        <v-icon icon="mdi-play" start />
        Execute Hunt
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { getDisplayCategory } from '@/utils/huntDisplayUtils'

const props = defineProps({
  hunt: {
    type: Object,
    required: true,
  },
})

defineEmits(['execute', 'view-details'])

// Computed properties
const categoryIcon = computed(() => {
  const iconMap = {
    person: 'mdi-account',
    domain: 'mdi-web',
    company: 'mdi-office-building',
    ip: 'mdi-ip-network',
    phone: 'mdi-phone',
    email: 'mdi-email',
    general: 'mdi-magnify',
  }
  return iconMap[props.hunt.category] || iconMap.general
})

const displayCategory = computed(() => {
  return getDisplayCategory(props.hunt.category)
})
</script>

<style scoped>
.hunt-card {
  height: 100%;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
}

.hunt-card:hover {
  transform: translateY(-2px);
}

.hunt-description {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 3.6em; /* Approximate height for 3 lines */
}
</style>
