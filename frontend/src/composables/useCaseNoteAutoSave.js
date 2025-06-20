import { watch } from 'vue'
import { caseService } from '../services/case'
import { useBaseNoteEditor } from './useBaseNoteEditor'

export function useCaseNoteAutoSave(props, emit) {
  const saveNotes = async () => {
    if (!editor.value) return

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
    triggerSave,
  } = useBaseNoteEditor({
    initialContent: props.modelValue || '',
    placeholder: 'Write your case notes here... Use / for commands.',
    editable: true,
    onUpdate: (editor) => {
      const content = editor.getHTML()
      emit('update:modelValue', content)
      triggerSave(saveNotes)
    },
    saveDelay: 1000,
  })

  // Watch for prop changes
  watch(
    () => props.modelValue,
    (newVal) => {
      updateContent(newVal)
    },
  )

  // Override cleanup to include save
  const enhancedCleanup = () => {
    cleanup(saveNotes)
  }

  return {
    editor,
    editorActions,
    saving,
    lastSavedTime,
    formatLastSaved,
    updateContent,
    cleanup: enhancedCleanup,
  }
}
