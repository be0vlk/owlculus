<template>
  <div>
    <!-- Normal Card View -->
    <v-card v-if="!expanded" variant="outlined" class="note-editor">
      <EditorToolbar
        :actions="editorActions"
        :saving="saving"
        :last-saved-time="lastSavedTime"
        :format-last-saved="formatLastSaved"
        :expanded="expanded"
        @toggle-expand="expanded = !expanded"
      />

      <v-card-text class="pa-4" style="min-height: 200px;">
        <editor-content :editor="editor" class="tiptap-content" />
      </v-card-text>
    </v-card>

    <!-- Full Screen Dialog View -->
    <v-dialog
      v-model="expanded"
      fullscreen
      transition="dialog-bottom-transition"
      :scrim="true"
    >
      <v-card class="d-flex flex-column" style="height: 100vh;">
        <v-toolbar color="primary" dark>
          <v-toolbar-title>
            <v-icon start>mdi-note-text</v-icon>
            Case Notes Editor
          </v-toolbar-title>
          <v-spacer />
          <v-btn
            icon="mdi-close"
            @click="expanded = false"
          />
        </v-toolbar>

        <div class="flex-grow-1 d-flex flex-column overflow-hidden">
          <EditorToolbar
            :actions="editorActions"
            :saving="saving"
            :last-saved-time="lastSavedTime"
            :format-last-saved="formatLastSaved"
            :expanded="expanded"
            @toggle-expand="expanded = !expanded"
          />

          <v-container fluid class="flex-grow-1 overflow-auto pa-6">
            <v-row justify="center">
              <v-col cols="12" lg="10" xl="8">
                <editor-content :editor="editor" class="tiptap-content fullscreen-editor" />
              </v-col>
            </v-row>
          </v-container>
        </div>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { EditorContent } from '@tiptap/vue-3'
import { watch, defineEmits, defineProps, ref } from 'vue'
import { useNoteEditor } from '../composables/useNoteEditor'
import EditorToolbar from './editor/EditorToolbar.vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  caseId: {
    type: Number,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])

const expanded = ref(false)

const {
  editor,
  editorActions,
  saving,
  lastSavedTime,
  formatLastSaved,
  updateContent,
} = useNoteEditor(props, emit)

watch(() => props.modelValue, updateContent)
</script>

<style scoped>
.note-editor .tiptap-content .ProseMirror {
  outline: none;
  min-height: 150px;
}

.note-editor .tiptap-content .ProseMirror p.is-editor-empty:first-child::before {
  color: rgb(var(--v-theme-on-surface-variant));
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}

/* TipTap editor content styling */
.note-editor .tiptap-content h1,
.note-editor .tiptap-content h2,
.note-editor .tiptap-content h3 {
  margin: 16px 0 8px;
  line-height: 1.2;
  font-weight: 600;
}

.note-editor .tiptap-content h1 { font-size: 1.5rem; }
.note-editor .tiptap-content h2 { font-size: 1.3rem; }
.note-editor .tiptap-content h3 { font-size: 1.1rem; }

.note-editor .tiptap-content ul,
.note-editor .tiptap-content ol {
  padding-left: 24px;
  margin: 8px 0;
}

.note-editor .tiptap-content blockquote {
  border-left: 4px solid rgb(var(--v-theme-primary));
  margin: 16px 0;
  padding-left: 16px;
  font-style: italic;
  color: rgb(var(--v-theme-on-surface-variant));
}

.note-editor .tiptap-content a {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}

.note-editor .tiptap-content p {
  margin: 8px 0;
}

/* Highlight styling */
.note-editor .tiptap-content mark {
  background-color: rgb(var(--v-theme-warning));
  padding: 0 2px;
  border-radius: 2px;
}

/* Task list styling */
.note-editor .tiptap-content .task-list {
  list-style: none;
  padding-left: 0;
}

.note-editor .tiptap-content .task-item {
  display: flex;
  align-items: flex-start;
  margin: 4px 0;
}

.note-editor .tiptap-content .task-item > label {
  flex: 0 0 auto;
  margin-right: 8px;
  margin-top: 2px;
  user-select: none;
}

.note-editor .tiptap-content .task-item > div {
  flex: 1 1 auto;
}

.note-editor .tiptap-content .task-item input[type="checkbox"] {
  margin: 0;
}

.note-editor .tiptap-content .task-item[data-checked="true"] > div {
  text-decoration: line-through;
  opacity: 0.6;
}

/* Full screen editor styles */
.fullscreen-editor .ProseMirror {
  outline: none;
  min-height: 400px;
  background: rgb(var(--v-theme-surface));
  border-radius: 4px;
  padding: 24px;
}

.fullscreen-editor .ProseMirror:focus {
  box-shadow: 0 0 0 2px rgba(var(--v-theme-primary), 0.2);
}

.fullscreen-editor .ProseMirror p.is-editor-empty:first-child::before {
  color: rgb(var(--v-theme-on-surface-variant));
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}
</style>