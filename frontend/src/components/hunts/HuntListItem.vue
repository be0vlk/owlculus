<template>
  <v-card
    class="hunt-list-item"
    variant="outlined"
    hover
    @click="$emit('view-details', hunt)"
  >
    <v-card-text class="pa-4">
      <v-row align="center">
        <!-- Hunt Icon and Basic Info -->
        <v-col cols="12" sm="4" class="d-flex align-center">
          <v-avatar :color="categoryColor" size="48" class="me-3">
            <v-icon :icon="categoryIcon" color="white" />
          </v-avatar>
          <div>
            <div class="text-h6 font-weight-bold">{{ hunt.display_name }}</div>
            <div class="text-caption text-uppercase">{{ hunt.category }}</div>
          </div>
        </v-col>

        <!-- Description -->
        <v-col cols="12" sm="4">
          <div class="text-body-2 text-medium-emphasis hunt-description">
            {{ hunt.description }}
          </div>
        </v-col>

        <!-- Stats and Actions -->
        <v-col cols="12" sm="4" class="d-flex align-center justify-end">
          <div class="d-flex flex-column align-end me-4">
            <!-- Status and Stats -->
            <div class="d-flex align-center mb-1">
              <v-chip
                :color="hunt.is_active ? 'success' : 'error'"
                size="small"
                variant="flat"
                class="me-2"
              >
                {{ hunt.is_active ? 'Active' : 'Inactive' }}
              </v-chip>
              <span class="text-caption">v{{ hunt.version }}</span>
            </div>
            
            <!-- Step Count -->
            <div class="d-flex align-center">
              <v-icon icon="mdi-play-box-multiple" size="small" class="me-1" />
              <span class="text-caption">{{ hunt.step_count || 0 }} steps</span>
            </div>
          </div>

          <!-- Execute Button -->
          <v-btn
            color="primary"
            variant="elevated"
            @click.stop="$emit('execute', hunt)"
            :disabled="!hunt.is_active"
          >
            <v-icon icon="mdi-play" start />
            Execute
          </v-btn>
        </v-col>
      </v-row>

      <!-- Required Parameters (collapsed view) -->
      <v-row v-if="requiredParams.length > 0" class="mt-2">
        <v-col cols="12">
          <div class="d-flex align-center">
            <span class="text-caption font-weight-bold me-2">Required Parameters:</span>
            <div class="d-flex flex-wrap ga-1">
              <v-chip
                v-for="param in requiredParams"
                :key="param"
                size="x-small"
                variant="outlined"
                color="primary"
              >
                {{ param }}
              </v-chip>
            </div>
          </div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

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
  const colorMap = {
    person: 'blue',
    domain: 'green',
    company: 'orange',
    ip: 'purple',
    phone: 'teal',
    email: 'red',
    general: 'grey'
  }
  return colorMap[props.hunt.category] || colorMap.general
})

const requiredParams = computed(() => {
  if (!props.hunt.initial_parameters) return []
  
  return Object.keys(props.hunt.initial_parameters).filter(
    key => props.hunt.initial_parameters[key]?.required
  )
})
</script>

<style scoped>
.hunt-list-item {
  cursor: pointer;
  transition: all 0.2s ease-in-out;
}

.hunt-list-item:hover {
  border-color: rgb(var(--v-theme-primary));
}

.hunt-description {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>