import { ref, watch } from 'vue'
import { entityService } from '../services/entity'
import { useBaseNoteEditor } from './useBaseNoteEditor'
import { useNoteSaveQueue } from './useNoteSaveQueue'

export function useEntityNoteEditor(entity, caseId, isEditing, formData, emit) {
  const saveError = ref('')
  let persistedEntity = entity.value
  const saveNotes = async () => {
    if (!editor.value || !entity.value) return true

    cancelPendingSave()
    const content = editor.value.getHTML()
    const target = entity.value
    const targetCaseId = caseId.value
    return saveQueue
      .save(content, async () => {
        const updatedEntity = await entityService.updateEntity(targetCaseId, target.id, {
          entity_type: target.entity_type,
          data: {
            ...(persistedEntity?.id === target.id ? persistedEntity.data : target.data),
            notes: content,
          },
        })
        persistedEntity = updatedEntity

        if (emit) {
          emit('edit', updatedEntity)
        }
      })
      .then(
        () => true,
        () => false,
      )
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
    label: 'Entity notes',
    initialContent: entity.value?.data?.notes || '',
    placeholder: isEditing.value
      ? 'Write your entity notes here... Use / for commands.'
      : 'Notes (read-only)',
    editable: isEditing.value,
    onExit: saveNotes,
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

  const saveQueue = useNoteSaveQueue({ saving, saveError, lastSaved, lastSavedTime })

  // Main-form writes use the same queue and acknowledge notes before edit mode ends.
  const saveEntity = (payload) => {
    cancelPendingSave()
    const content = editor.value.getHTML()
    const targetId = entity.value.id
    const targetCaseId = caseId.value
    return saveQueue.save(
      content,
      async () => {
        const updatedEntity = await entityService.updateEntity(targetCaseId, targetId, payload)
        persistedEntity = updatedEntity
        return updatedEntity
      },
      { force: true },
    )
  }

  watch(entity, (newEntity) => {
    persistedEntity = newEntity
  })

  // Watch for entity changes and update editor content
  watch(
    () => entity.value?.data?.notes,
    (newNotes) => {
      if (newNotes !== undefined && editor.value) {
        if (saving.value || newNotes === lastSaved.value) return
        updateContent(newNotes)
      }
    },
    { immediate: true },
  )

  // Watch for editing state changes and update editor editability
  watch(
    () => isEditing.value,
    (newEditingState, oldEditingState) => {
      if (editor.value) {
        if (newEditingState && formData?.value) {
          const content = editor.value.getHTML()
          if (content !== lastSaved.value || persistedEntity !== entity.value) {
            formData.value.data.notes = content
          }
        }
        // If exiting edit mode, save any pending changes first
        if (oldEditingState && !newEditingState) {
          saveNotes()
        }
        editor.value.setEditable(newEditingState, false)
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
    saveError,
    lastSavedTime,
    formatLastSaved,
    updateContent,
    cleanup: enhancedCleanup,
    saveNotes,
    saveEntity,
  }
}
