<template>
  <v-card
    class="hunt-list-item"
    :style="{ borderLeftColor: `rgb(var(--v-theme-${categoryColor}))` }"
    variant="outlined"
    hover
    @click="$emit('view-details', hunt)"
  >
    <v-card-text class="pa-3">
      <v-row class="align-center">
        <v-col cols="12" md="5" class="d-flex align-center">
          <v-avatar :color="categoryColor" size="40" class="me-3">
            <v-icon :icon="getCategoryIcon(hunt.category)" size="small" color="white" />
          </v-avatar>
          <div>
            <div class="d-flex align-center">
              <span class="text-body-large font-weight-bold">{{ hunt.display_name }}</span>
              <v-icon
                v-if="!hunt.is_active"
                color="error"
                icon="mdi-alert-circle"
                size="x-small"
                class="ml-2"
                :title="'Inactive'"
              />
            </div>
            <div class="text-body-small text-medium-emphasis">{{ displayCategory }}</div>
          </div>
        </v-col>

        <v-col cols="12" md="3">
          <div class="text-body-medium text-medium-emphasis hunt-description">
            {{ hunt.description }}
          </div>
        </v-col>

        <v-col cols="12" md="4" class="d-flex align-center justify-md-end justify-start">
          <div class="text-body-small text-medium-emphasis me-3">
            {{ hunt.step_count || 0 }} steps
          </div>

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
import { getCategoryColor, getCategoryIcon, getDisplayCategory } from '@/utils/huntDisplayUtils'

const props = defineProps({
  hunt: {
    type: Object,
    required: true,
  },
})

defineEmits(['execute', 'view-details'])

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
  box-shadow: 0 2px 8px rgb(0 0 0 / 10%);
}

.hunt-description {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}

.hunt-list-item:hover::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgb(var(--v-theme-primary), 0.02);
  pointer-events: none;
}
</style>
