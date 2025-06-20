import { watch } from 'vue'
import { useBaseNoteEditor } from './useBaseNoteEditor'

export function useCaseNoteManualSave(props, emit) {
  // For case notes, we don't auto-save - parent component handles saving via Save button
  const { editor, editorActions, saving, lastSavedTime, formatLastSaved, updateContent, cleanup } =
    useBaseNoteEditor({
      initialContent: props.modelValue || '',
      placeholder: props.isEditing
        ? 'Write your case notes here... Use / for commands.'
        : 'Notes (read-only)',
      editable: props.isEditing,
      onUpdate: (editor) => {
        const content = editor.getHTML()
        if (props.isEditing) {
          emit('update:modelValue', content)
        }
      },
    })

  // Watch for content changes from parent
  watch(
    () => props.modelValue,
    (newVal) => {
      updateContent(newVal)
    },
  )

  // Watch for editing state changes and update editor editability
  watch(
    () => props.isEditing,
    (newEditingState) => {
      if (editor.value) {
        editor.value.setEditable(newEditingState)
      }
    },
  )

  return {
    editor,
    editorActions,
    saving,
    lastSavedTime,
    formatLastSaved,
    updateContent,
    cleanup,
  }
}
