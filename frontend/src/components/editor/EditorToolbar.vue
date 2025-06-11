<template>
  <v-toolbar density="compact" color="surface" class="border-b">
    <v-btn-group variant="text" density="compact">
      <v-btn
        v-for="(action, index) in actions"
        :key="index"
        :icon="action.icon"
        size="small"
        :variant="action.isActive?.() ? 'tonal' : 'text'"
        :color="action.isActive?.() ? 'primary' : 'default'"
        @click="action.action"
        :title="action.title"
      />
    </v-btn-group>
    
    <v-spacer />
    
    <div class="text-caption text-medium-emphasis mr-3">
      <v-progress-circular
        v-if="saving"
        size="16"
        width="2"
        indeterminate
        class="mr-2"
      />
      <span v-if="saving">Saving...</span>
      <span v-else-if="lastSavedTime">Last saved: {{ formatLastSaved }}</span>
    </div>
    
    <v-btn
      :icon="expanded ? 'mdi-arrow-collapse' : 'mdi-arrow-expand'"
      size="small"
      variant="text"
      :title="expanded ? 'Exit fullscreen' : 'Expand to fullscreen'"
      @click="$emit('toggle-expand')"
    />
  </v-toolbar>
</template>

<script setup>
defineProps({
  actions: {
    type: Array,
    required: true,
  },
  saving: {
    type: Boolean,
    default: false,
  },
  lastSavedTime: {
    type: Date,
    default: null,
  },
  formatLastSaved: {
    type: String,
    default: '',
  },
  expanded: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['toggle-expand'])
</script>