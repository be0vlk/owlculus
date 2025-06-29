<template>
  <v-card
    class="hunt-list-item"
    :class="`category-${hunt.category}`"
    variant="outlined"
    hover
    @click="$emit('view-details', hunt)"
  >
    <v-card-text class="pa-3">
      <v-row align="center">
        <!-- Hunt Icon and Basic Info -->
        <v-col cols="12" md="5" class="d-flex align-center">
          <v-avatar :color="categoryColor" size="40" class="me-3">
            <v-icon :icon="categoryIcon" size="small" color="white" />
          </v-avatar>
          <div>
            <div class="d-flex align-center">
              <span class="text-body-1 font-weight-bold">{{ hunt.display_name }}</span>
              <v-icon 
                v-if="!hunt.is_active" 
                icon="mdi-alert-circle" 
                size="x-small" 
                color="error" 
                class="ml-2"
                :title="'Inactive'"
              />
            </div>
            <div class="text-caption text-medium-emphasis">{{ displayCategory }}</div>
          </div>
        </v-col>

        <!-- Description -->
        <v-col cols="12" md="3">
          <div class="text-body-2 text-medium-emphasis hunt-description">
            {{ hunt.description }}
          </div>
        </v-col>

        <!-- Stats and Actions -->
        <v-col cols="12" md="4" class="d-flex align-center justify-md-end justify-start">
          <div class="text-caption text-medium-emphasis me-3">
            {{ hunt.step_count || 0 }} steps
          </div>
          
          <!-- Execute Button -->
          <v-btn
            color="primary"
            variant="tonal"
            size="small"
            @click.stop="$emit('execute', hunt)"
            :disabled="!hunt.is_active"
          >
            <v-icon icon="mdi-play" start />
            Execute
          </v-btn>
        </v-col>
      </v-row>


    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { getCategoryColor, getDisplayCategory } from '@/utils/huntDisplayUtils'

const props = defineProps({
  hunt: {
    type: Object,
    required: true
  }
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
    general: 'mdi-magnify'
  }
  return iconMap[props.hunt.category] || iconMap.general
})

const categoryColor = computed(() => {
  return getCategoryColor(props.hunt.category)
})

const displayCategory = computed(() => {
  return getDisplayCategory(props.hunt.category)
})
</script>

<style scoped>
.hunt-list-item {
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  border-left: 4px solid transparent;
  position: relative;
  overflow: hidden;
}

.hunt-list-item:hover {
  transform: translateX(2px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* Category-specific left border colors */
.hunt-list-item.category-person {
  border-left-color: rgb(var(--v-theme-primary));
}

.hunt-list-item.category-domain,
.hunt-list-item.category-network {
  border-left-color: rgb(var(--v-theme-info));
}

.hunt-list-item.category-company {
  border-left-color: rgb(var(--v-theme-warning));
}

.hunt-list-item.category-ip {
  border-left-color: rgb(var(--v-theme-secondary));
}

.hunt-list-item.category-phone {
  border-left-color: rgb(var(--v-theme-primary-darken-1));
}

.hunt-list-item.category-email {
  border-left-color: rgb(var(--v-theme-error));
}

.hunt-list-item.category-general,
.hunt-list-item.category-other {
  border-left-color: rgb(var(--v-theme-secondary));
}

.hunt-description {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}

/* Add subtle background on hover */
.hunt-list-item:hover::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgb(var(--v-theme-primary), 0.02);
  pointer-events: none;
}
</style>