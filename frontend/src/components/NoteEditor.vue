<template>
  <div ref="container">
    <!-- Normal View -->
    <component
      :is="variant === 'card' ? 'v-card' : 'div'"
      v-if="!expanded"
      :variant="variant === 'card' ? 'outlined' : undefined"
      :class="variant === 'card' ? 'note-editor' : 'note-editor-container'"
    >
      <EditorToolbar
        :actions="editorActions"
        :disabled="isEditing === false"
        :saving="saving"
        :last-saved-time="lastSavedTime"
        :format-last-saved="formatLastSaved"
        :expanded="expanded"
        @toggle-expand="expanded = !expanded"
      />

      <component
        :is="variant === 'card' ? 'v-card-text' : 'div'"
        class="pa-4"
        :class="{ 'read-only-notes': isEditing === false }"
        style="min-height: 200px"
      >
        <editor-content :editor="editor" class="tiptap-content" />
      </component>
    </component>

    <!-- Full Screen Dialog View -->
    <v-alert v-if="saveError && !expanded" type="error">{{ saveError }}</v-alert>
    <v-dialog
      aria-label="Case Notes Editor"
      v-model="expanded"
      :scrim="true"
      fullscreen
      transition="dialog-bottom-transition"
    >
      <v-card class="d-flex flex-column" style="height: 100vh">
        <v-toolbar color="primary">
          <v-toolbar-title>
            <v-icon start>mdi-note-text</v-icon>
            Case Notes Editor
          </v-toolbar-title>
          <v-spacer />
          <v-chip
            v-if="isEditing !== undefined"
            :color="isEditing ? 'warning' : 'primary'"
            variant="tonal"
            size="small"
            class="me-3"
          >
            {{ isEditing ? 'Editing' : 'View Mode' }}
          </v-chip>
          <v-btn aria-label="Close notes" icon="mdi-close" @click="expanded = false" />
        </v-toolbar>

        <div class="flex-grow-1 d-flex flex-column overflow-hidden">
          <EditorToolbar
            :actions="editorActions"
            :disabled="isEditing === false"
            :saving="saving"
            :last-saved-time="lastSavedTime"
            :format-last-saved="formatLastSaved"
            :expanded="expanded"
            @toggle-expand="expanded = !expanded"
          />

          <v-alert v-if="saveError" type="error">{{ saveError }}</v-alert>
          <v-container fluid class="flex-grow-1 overflow-auto pa-6">
            <v-row class="justify-center">
              <v-col cols="12" lg="10" xl="8">
                <div :class="{ 'read-only-notes': isEditing === false }">
                  <editor-content :editor="editor" class="tiptap-content fullscreen-editor" />
                </div>
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
import { ref } from 'vue'
import { useCaseNoteSave } from '../composables/useCaseNoteSave'
import { useDialogFocusRestore } from '../composables/useDialogFocusRestore'
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
  isEditing: {
    type: Boolean,
    default: undefined,
  },
  saveMode: {
    type: String,
    default: 'auto',
    validator: (value) => ['auto', 'manual'].includes(value),
  },
  variant: {
    type: String,
    default: 'card',
    validator: (value) => ['card', 'plain'].includes(value),
  },
})

const emit = defineEmits(['update:modelValue'])

const expanded = ref(false)
const container = ref(null)
useDialogFocusRestore(
  () => expanded.value,
  () => container.value?.querySelector('[aria-label="Expand to fullscreen"]'),
)

const { editor, editorActions, saving, saveError, lastSavedTime, formatLastSaved } =
  useCaseNoteSave(props, emit, {
    saveMode: props.saveMode,
  })
</script>

<style scoped>
/* Full screen rules come first so the more specific embedded editor rules can refine them. */
.fullscreen-editor :deep(.ProseMirror) {
  outline: none;
  min-height: 400px;
  background: rgb(var(--v-theme-surface));
  border-radius: 4px;
  padding: 24px;
}

.fullscreen-editor :deep(.ProseMirror:focus) {
  box-shadow: 0 0 0 2px rgb(var(--v-theme-primary), 0.2);
}

.fullscreen-editor :deep(.ProseMirror .is-editor-empty:first-child::before) {
  color: rgb(var(--v-theme-on-surface));
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}

.tiptap-content :deep(.ProseMirror) {
  outline: none;
  min-height: 150px;
}

.tiptap-content :deep(.ProseMirror .is-editor-empty:first-child::before) {
  color: rgb(var(--v-theme-on-surface));
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}

/* TipTap editor content styling */
.note-editor .tiptap-content :deep(h1),
.note-editor .tiptap-content :deep(h2),
.note-editor .tiptap-content :deep(h3),
.note-editor-container .tiptap-content :deep(h1),
.note-editor-container .tiptap-content :deep(h2),
.note-editor-container .tiptap-content :deep(h3) {
  margin: 16px 0 8px;
  line-height: 1.2;
  font-weight: 600;
}

.tiptap-content :deep(h1) {
  font-size: 1.5rem;
}

.tiptap-content :deep(h2) {
  font-size: 1.3rem;
}

.tiptap-content :deep(h3) {
  font-size: 1.1rem;
}

.note-editor .tiptap-content :deep(ul),
.note-editor .tiptap-content :deep(ol),
.note-editor-container .tiptap-content :deep(ul),
.note-editor-container .tiptap-content :deep(ol) {
  padding-left: 24px;
  margin: 8px 0;
}

.tiptap-content :deep(blockquote) {
  border-left: 4px solid rgb(var(--v-theme-primary));
  margin: 16px 0;
  padding-left: 16px;
  font-style: italic;
  color: rgb(var(--v-theme-on-surface));
}

.tiptap-content :deep(a) {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}

.tiptap-content :deep(p) {
  margin: 8px 0;
}

/* Highlight styling */
.tiptap-content :deep(mark) {
  background-color: rgb(var(--v-theme-warning));
  color: rgb(var(--v-theme-on-warning));
  padding: 0 2px;
  border-radius: 2px;
}

/* Read-only styling */
.read-only-notes {
  background-color: rgb(var(--v-theme-surface-variant), 0.05);
}

.read-only-notes .tiptap-content :deep(.ProseMirror) {
  cursor: default;
  background-color: rgb(var(--v-theme-surface-variant), 0.03);
}

.read-only-notes .tiptap-content :deep(.ProseMirror *) {
  pointer-events: none;
}

.tiptap-content :deep(.tiptap-editor:focus-visible) {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}
</style>
