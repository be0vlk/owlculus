<template>
  <div class="editor-toolbar border-b" role="group" aria-label="Note formatting and view controls">
    <div class="editor-formatting" role="group" aria-label="Text formatting">
      <v-btn
        v-for="(action, index) in actions"
        :key="index"
        :icon="action.icon"
        size="small"
        :variant="action.isActive?.() ? 'tonal' : 'text'"
        :color="action.isActive?.() ? 'primary' : 'default'"
        @click="action.action"
        :title="action.title"
        :aria-label="action.title"
        :aria-pressed="Boolean(action.isActive?.())"
        :disabled="disabled"
      />
    </div>

    <div class="editor-save-status text-body-small" role="status" aria-live="polite">
      <v-progress-circular v-if="saving" class="mr-2" indeterminate size="16" width="2" />
      <span v-if="saving">Saving...</span>
      <span v-else-if="lastSavedTime">Last saved: {{ formatLastSaved }}</span>
    </div>

    <v-btn
      :icon="expanded ? 'mdi-arrow-collapse' : 'mdi-arrow-expand'"
      size="small"
      variant="text"
      :aria-label="expanded ? 'Exit fullscreen' : 'Expand to fullscreen'"
      :title="expanded ? 'Exit fullscreen' : 'Expand to fullscreen'"
      @click="$emit('toggle-expand')"
    />
  </div>
</template>

<script setup>
defineProps({
  disabled: { type: Boolean, default: false },
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

<style scoped>
.editor-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px;
  color: rgb(var(--v-theme-on-surface));
  background: rgb(var(--v-theme-surface));
}

.editor-formatting {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  flex: 1 1 280px;
}

.editor-save-status {
  margin-left: auto;
}
</style>
