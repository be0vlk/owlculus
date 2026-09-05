import { ref, watch } from 'vue'
import { caseService } from '../services/case'
import { useBaseNoteEditor } from './useBaseNoteEditor'
import { useNoteSaveQueue } from './useNoteSaveQueue'

export function useCaseNoteSave(props, emit, options = {}) {
  const saveError = ref('')
  const { saveMode = 'auto', saveDelay = 1000 } = options

  const saveNotes = async () => {
    if (!editor.value || saveMode !== 'auto') return

    cancelPendingSave()
    const content = editor.value.getHTML()
    const caseId = props.caseId
    await saveQueue
      .save(content, () => caseService.updateCase(caseId, { notes: content }))
      .catch(() => {})
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
    triggerSave,
    cancelPendingSave,
  } = useBaseNoteEditor({
    label: 'Case notes',
    initialContent: props.modelValue || '',
    placeholder:
      props.isEditing !== false
        ? 'Write your case notes here... Use / for commands.'
        : 'Notes (read-only)',
    editable: props.isEditing !== false,
    onExit: saveMode === 'auto' ? saveNotes : null,
    onUpdate: (editor) => {
      const content = editor.getHTML()
      if (props.isEditing !== false) {
        emit('update:modelValue', content)
        if (saveMode === 'auto') {
          triggerSave(saveNotes)
        }
      }
    },
    saveDelay: saveMode === 'auto' ? saveDelay : null,
  })

  const saveQueue = useNoteSaveQueue({ saving, saveError, lastSaved, lastSavedTime })

  // Watch for prop changes
  watch(
    () => props.modelValue,
    (newVal) => {
      updateContent(newVal)
    },
  )

  // Watch for editing state changes and update editor editability
  if (props.isEditing !== undefined) {
    watch(
      () => props.isEditing,
      (newEditingState) => {
        if (editor.value) {
          if (!newEditingState) saveNotes()
          editor.value.setEditable(newEditingState, false)
        }
      },
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
    saveError,
    lastSavedTime,
    formatLastSaved,
    updateContent,
    cleanup: enhancedCleanup,
  }
}
