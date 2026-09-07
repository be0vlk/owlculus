import { useEntityAdvisories } from './useEntityAdvisories'
import { ref, computed, watch } from 'vue'
import { entityService } from '../services/entity'
import { entitySchemas } from './entitySchemas'
import { cleanFormData } from '../utils/cleanFormData'
import { getErrorMessage } from '../utils/errorMessage'
import { useBaseNoteEditor } from './useBaseNoteEditor'
import { useNoteSaveQueue } from './useNoteSaveQueue'
import { useEntityValidation, entityIdentityGuidance } from './useEntityValidation'
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
  // The Case-and-Entity keyed dialog owns one target for its entire lifetime,
  // including queued writes that finish after the dialog is replaced.
  const targetCaseId = caseId.value
  const targetId = entity.value.id
  const targetType = entity.value.entity_type
  const advisories = useEntityAdvisories(targetCaseId, targetId)
  const error = ref('')
  const isEditing = ref(false)
  const updating = ref(false)
  const activeTab = ref('basicInfo')
  const acknowledgedEntity = ref(clone(entity.value))
  let hasPersisted = false
  const formData = ref({ data: draftData(acknowledgedEntity.value.data) })
  const entitySchema = computed(() => entitySchemas[acknowledgedEntity.value.entity_type])

  const acknowledgeEntity = (updatedEntity) => {
    acknowledgedEntity.value = clone(updatedEntity)
    hasPersisted = true
  }

  const startEditing = () => {
    formData.value = { data: draftData(acknowledgedEntity.value.data) }
    isEditing.value = true
  }

  const cancelEdit = () => {
    advisories.clear()
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

  const updateEntity = async (confirmed = false) => {
    try {
      updating.value = true
      error.value = ''
      if (targetType === 'domain') {
        const result = useEntityValidation().domainRule(formData.value.data.domain)
        if (result !== true) throw new Error(result)
      }
      if (
        ['person', 'vehicle'].includes(targetType) &&
        !useEntityValidation().isFormValid(targetType, formData.value.data)
      )
        throw new Error(entityIdentityGuidance[targetType])
      const payload = { entity_type: targetType, data: cleanFormData(clone(formData.value.data)) }
      if (!(await advisories.check(payload, confirmed))) return null
      const updatedEntity = await saveEntity({
        entity_type: targetType,
        data: draftData(payload.data),
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
    // Parent refreshes can arrive out of order. After a local write, only a proven newer
    // revision may replace its acknowledgement, including when this mounted dialog reopens.
    if (
      hasPersisted &&
      !(Date.parse(newEntity.updated_at) > Date.parse(acknowledgedEntity.value.updated_at))
    )
      return
    acknowledgedEntity.value = clone(newEntity)
    if (!isEditing.value) formData.value = { data: draftData(newEntity.data) }
  })

  const saveError = ref('')
  const noteSaveError = computed(() => {
    if (!saveError.value) return ''
    const retry = isEditing.value ? 'Retry with Save Changes.' : 'Retry with Close or Edit Entity.'
    return `${saveError.value} ${retry}`
  })
  const saveNotes = async () => {
    if (!editor.value) return true

    cancelPendingSave()
    const content = editor.value.getHTML()
    return saveQueue
      .save(content, async () => {
        const updatedEntity = await entityService.updateEntity(targetCaseId, targetId, {
          entity_type: targetType,
          data: {
            ...clone(acknowledgedEntity.value.data),
            notes: content,
          },
        })
        acknowledgeEntity(updatedEntity)

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
    onUpdate: () => {
      if (isEditing.value) {
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
    // Keep unchanged empty/legacy HTML conventions, otherwise submit the captured editor text.
    const submittedPayload = {
      ...payload,
      data: {
        ...payload.data,
        notes: content === lastSaved.value ? acknowledgedEntity.value.data.notes || '' : content,
      },
    }
    return saveQueue.save(
      content,
      async () => {
        const updatedEntity = await entityService.updateEntity(
          targetCaseId,
          targetId,
          submittedPayload,
        )
        acknowledgeEntity(updatedEntity)
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
        // If exiting edit mode, save any pending changes first
        if (oldEditingState && !newEditingState) {
          saveNotes()
        }
        editor.value.setEditable(newEditingState, false)
      }
    },
  )

  return {
    advisories,
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
    saveError: noteSaveError,
    lastSavedTime,
    formatLastSaved,
    saveNotes,
  }
}
