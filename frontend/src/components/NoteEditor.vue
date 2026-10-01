<template>
  <div ref="container">
    <div v-if="!expanded">
      <EditorToolbar
        :actions="editorActions"
        :disabled="!isEditing"
        @toggle-expand="expanded = true"
      />
      <div class="pa-4" :class="{ 'read-only-notes': !isEditing }" style="min-height: 200px">
        <editor-content :editor="editor" class="tiptap-content" />
      </div>
    </div>

    <EntityNotesFullscreen
      v-model:show="expanded"
      title="Case"
      :editor="editor"
      :editor-actions="editorActions"
      :is-editing="isEditing"
      @close="expanded = false"
    />
  </div>
</template>

<script setup>
import { EditorContent } from '@tiptap/vue-3'
import { ref, watch } from 'vue'
import { useBaseNoteEditor } from '../composables/useBaseNoteEditor'
import { useDialogFocusRestore } from '../composables/useDialogFocusRestore'
import EditorToolbar from './editor/EditorToolbar.vue'
import EntityNotesFullscreen from './entities/EntityNotesFullscreen.vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  isEditing: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue'])

const expanded = ref(false)
const container = ref(null)
useDialogFocusRestore(
  () => expanded.value,
  () => container.value?.querySelector('[aria-label="Expand to fullscreen"]'),
)

// Saving is manual: the parent persists the emitted HTML.
const { editor, editorActions, updateContent } = useBaseNoteEditor({
  label: 'Case notes',
  initialContent: props.modelValue,
  placeholder: props.isEditing
    ? 'Write your case notes here... Use / for commands.'
    : 'Notes (read-only)',
  editable: props.isEditing,
  onUpdate: (editor) => {
    if (props.isEditing) emit('update:modelValue', editor.getHTML())
  },
})

watch(() => props.modelValue, updateContent)
watch(
  () => props.isEditing,
  (editing) => editor.value?.setEditable(editing, false),
)
</script>
