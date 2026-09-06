import { ref, computed, watch } from 'vue'
import { entityService } from '../services/entity'
import { entitySchemas } from './entitySchemas'
import { cleanFormData } from '../utils/cleanFormData'
import { getErrorMessage } from '../utils/errorMessage'
import { useBaseNoteEditor } from './useBaseNoteEditor'
import { useNoteSaveQueue } from './useNoteSaveQueue'
import { useEntitySources } from './useEntitySources'

// Entity transport data is JSON. Copy recursively, including arrays, to isolate Vue proxies too.
const clone = (value) => JSON.parse(JSON.stringify(value))

function draftData(data) {
  return {
    ...clone(data),
    aliases: Array.isArray(data.aliases) ? clone(data.aliases) : [],
    address: clone(data.address || {}),
    social_media: clone(data.social_media || {}),
    associates: clone(data.associates || {}),
    executives: clone(data.executives || {}),
    affiliates: clone(data.affiliates || {}),
    notes: data.notes || '',
  }
}

export function useEntityDetails(entity, caseId, emit) {
  const error = ref('')
  const isEditing = ref(false)
  const updating = ref(false)
  const activeTab = ref('basicInfo')
  const acknowledgedEntity = ref(clone(entity.value))
  const formData = ref({ data: draftData(acknowledgedEntity.value.data) })
  const entitySchema = computed(() => entitySchemas[acknowledgedEntity.value.entity_type])

  const startEditing = () => {
    formData.value = { data: draftData(acknowledgedEntity.value.data) }
    isEditing.value = true
  }

  const cancelEdit = () => {
    formData.value = { data: draftData(acknowledgedEntity.value.data) }
    isEditing.value = false
    error.value = ''
  }

  const getFieldValue = (parentField, fieldId) => {
    const data = parentField ? formData.value.data[parentField] : formData.value.data
    return data?.[fieldId] ?? ''
  }

  const updateFieldValue = (parentField, fieldId, value) => {
    const data = formData.value.data
    if (parentField) {
      data[parentField] ||= {}
      data[parentField][fieldId] = value
    } else {
      data[fieldId] = value
    }
  }

  const { getSourceValue, updateSourceValue } = useEntitySources(
    acknowledgedEntity,
    formData,
    isEditing,
  )

  const updateEntity = async () => {
    try {
      updating.value = true
      error.value = ''
      const updatedEntity = await saveEntity({
        entity_type: acknowledgedEntity.value.entity_type,
        data: draftData(cleanFormData(clone(formData.value.data))),
      })
      isEditing.value = false
      emit?.('edit', updatedEntity)
      return updatedEntity
    } catch (err) {
      error.value = getErrorMessage(err, 'Failed to update entity')
      throw err
    } finally {
      updating.value = false
    }
  }

  // The parent keys the dialog by Case and Entity. Same-session refreshes must leave drafts alone.
  watch(entity, (newEntity) => {
    acknowledgedEntity.value = clone(newEntity)
    if (!isEditing.value) formData.value = { data: draftData(newEntity.data) }
  })

  const saveError = ref('')
  const saveNotes = async () => {
    if (!editor.value || !entity.value) return true

    cancelPendingSave()
    const content = editor.value.getHTML()
    const target = clone(acknowledgedEntity.value)
    const targetCaseId = caseId.value
    return saveQueue
      .save(content, async () => {
        const updatedEntity = await entityService.updateEntity(targetCaseId, target.id, {
          entity_type: target.entity_type,
          data: {
            ...clone(
              acknowledgedEntity.value?.id === target.id
                ? acknowledgedEntity.value.data
                : target.data,
            ),
            notes: content,
          },
        })
        acknowledgedEntity.value = clone(updatedEntity)

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
        formData.value.data.notes = content
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
        acknowledgedEntity.value = clone(updatedEntity)
        return updatedEntity
      },
      { force: true },
    )
  }

  // Watch for entity changes and update editor content
  watch(
    () => acknowledgedEntity.value?.data?.notes,
    (newNotes) => {
      if (newNotes !== undefined && editor.value) {
        if (saving.value || newNotes === lastSaved.value) return
        if (editor.value.getHTML() !== lastSaved.value) return
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
        if (newEditingState) {
          const content = editor.value.getHTML()
          if (content !== lastSaved.value) {
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

  return {
    error,
    isEditing,
    updating,
    activeTab,
    entitySchema,
    acknowledgedEntity,
    startEditing,
    cancelEdit,
    updateEntity,
    getFieldValue,
    updateFieldValue,
    getSourceValue,
    updateSourceValue,
    editor,
    editorActions,
    saving,
    saveError,
    lastSavedTime,
    formatLastSaved,
    saveNotes,
  }
}
