<template>
  <v-dialog
    :model-value="show"
    @update:model-value="$emit('update:show', $event)"
    fullscreen
    transition="dialog-bottom-transition"
    :scrim="true"
  >
    <v-card class="d-flex flex-column" style="height: 100vh">
      <v-toolbar color="primary" dark>
        <v-toolbar-title>
          <v-icon start>mdi-note-text</v-icon>
          {{ title }} - Notes
        </v-toolbar-title>
        <v-spacer />
        <v-btn icon="mdi-close" @click="$emit('close')" />
      </v-toolbar>

      <div class="flex-grow-1 d-flex flex-column overflow-hidden">
        <EditorToolbar
          v-if="editor"
          :actions="editorActions"
          :saving="saving"
          :last-saved-time="lastSavedTime"
          :format-last-saved="formatLastSaved"
          :expanded="true"
          @toggle-expand="$emit('close')"
        />

        <v-container fluid class="flex-grow-1 overflow-auto pa-6">
          <v-row justify="center">
            <v-col cols="12" lg="10" xl="8">
              <div :class="{ 'read-only-notes': isEditing === false }">
                <editor-content
                  v-if="editor"
                  :editor="editor"
                  class="tiptap-content fullscreen-editor"
                />
                <div v-else class="text-center pa-4 text-grey">
                  <v-icon size="64">mdi-note-text</v-icon>
                  <p>Loading notes editor...</p>
                </div>
              </div>
            </v-col>
          </v-row>
        </v-container>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { EditorContent } from '@tiptap/vue-3'
import EditorToolbar from '../editor/EditorToolbar.vue'

defineProps({
  show: { type: Boolean, required: true },
  title: { type: String, required: true },
  editor: { type: Object, default: null },
  editorActions: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
  lastSavedTime: { type: [Date, null], default: null },
  formatLastSaved: { type: String, default: '' },
  isEditing: { type: Boolean, default: undefined },
})

defineEmits(['update:show', 'close'])
</script>

<style scoped>
@import '../../styles/entity-editor.css';

/* Read-only styling for fullscreen notes */
.read-only-notes .tiptap-content .ProseMirror {
  cursor: default;
  background-color: rgb(var(--v-theme-surface-variant), 0.03) !important;
}

.read-only-notes .tiptap-content .ProseMirror * {
  pointer-events: none;
}
</style>
