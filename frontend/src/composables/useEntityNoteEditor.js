import { watch } from 'vue'
import { entityService } from '../services/entity'
import { useBaseNoteEditor } from './useBaseNoteEditor'

export function useEntityNoteEditor(entity, caseId, isEditing, formData, emit) {
  const saveNotes = async () => {
    if (!editor.value || !entity.value || !isEditing.value) return

    const content = editor.value.getHTML()
    if (content === lastSaved.value) return

    try {
      saving.value = true

      const updatedEntity = await entityService.updateEntity(caseId.value, entity.value.id, {
        entity_type: entity.value.entity_type,
        data: {
          ...entity.value.data,
          notes: content,
        },
      })

      lastSaved.value = content
      lastSavedTime.value = new Date()

      if (emit) {
        emit('edit', updatedEntity)
      }
    } catch (error) {
      console.error('Failed to save entity notes:', error)
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
    initialContent: entity.value?.data?.notes || '',
    placeholder: isEditing.value
      ? 'Write your entity notes here... Use / for commands.'
      : 'Notes (read-only)',
    editable: isEditing.value,
    onUpdate: (editor) => {
      const content = editor.getHTML()
      if (isEditing.value) {
        // Update the form data so main form save includes latest notes
        if (formData && formData.value) {
          formData.value.data.notes = content
        }
        triggerSave(saveNotes)
      }
    },
    saveDelay: 5000,
  })

  // Watch for entity changes and update editor content
  watch(
    () => entity.value?.data?.notes,
    (newNotes) => {
      if (newNotes !== undefined && editor.value) {
        updateContent(newNotes)
        lastSaved.value = newNotes || ''
      }
    },
    { immediate: true },
  )

  // Watch for editing state changes and update editor editability
  watch(
    () => isEditing.value,
    (newEditingState, oldEditingState) => {
      if (editor.value) {
        // If exiting edit mode, save any pending changes first
        if (oldEditingState && !newEditingState) {
          const content = editor.value.getHTML()
          if (content !== lastSaved.value) {
            saveNotes()
          }
        }
        editor.value.setEditable(newEditingState)
      }
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
    saveNotes,
  }
}
