import { watch } from 'vue'
import { caseService } from '../services/case'
import { useBaseNoteEditor } from './useBaseNoteEditor'

export function useCaseNoteSave (props, emit, options = {}) {
  const { saveMode = 'auto', saveDelay = 1000 } = options

  const saveNotes = async () => {
    if (!editor.value || saveMode !== 'auto') return

    const content = editor.value.getHTML()
    if (content === lastSaved.value) return

    try {
      saving.value = true
      await caseService.updateCase(props.caseId, { notes: content })
      lastSaved.value = content
      lastSavedTime.value = new Date()
    } catch (error) {
      console.error('Failed to save notes:', error)
    } finally {
      saving.value = false
    }
  }

  const {
    editor,
    editorActions,
    saving,
    lastSaved,
    lastSavedTime,
    formatLastSaved,
    updateContent,
    cleanup,
    triggerSave
  } = useBaseNoteEditor({
    initialContent: props.modelValue || '',
    placeholder: props.isEditing !== false
      ? 'Write your case notes here... Use / for commands.'
      : 'Notes (read-only)',
    editable: props.isEditing !== false,
    onUpdate: (editor) => {
      const content = editor.getHTML()
      if (props.isEditing !== false) {
        emit('update:modelValue', content)
        if (saveMode === 'auto') {
          triggerSave(saveNotes)
        }
      }
    },
    saveDelay: saveMode === 'auto' ? saveDelay : null
  })

  // Watch for prop changes
  watch(
    () => props.modelValue,
    (newVal) => {
      updateContent(newVal)
    }
  )

  // Watch for editing state changes and update editor editability
  if (props.isEditing !== undefined) {
    watch(
      () => props.isEditing,
      (newEditingState) => {
        if (editor.value) {
          editor.value.setEditable(newEditingState)
        }
      }
    )
  }

  // Override cleanup to include save for auto-save mode
  const enhancedCleanup = () => {
    if (saveMode === 'auto') {
      cleanup(saveNotes)
    } else {
      cleanup()
    }
  }

  return {
    editor,
    editorActions,
    saving,
    lastSavedTime,
    formatLastSaved,
    updateContent,
    cleanup: enhancedCleanup
  }
}
