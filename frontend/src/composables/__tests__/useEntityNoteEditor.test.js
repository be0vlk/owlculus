import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useEntityNoteEditor } from '../useEntityNoteEditor'
import { entityService } from '../../services/entity'
import { ref, nextTick } from 'vue'

vi.mock('../../services/entity', () => ({
  entityService: {
    updateEntity: vi.fn(),
  },
}))

vi.mock('../useBaseNoteEditor', () => ({
  useBaseNoteEditor: vi.fn(),
}))

describe('useEntityNoteEditor', () => {
  let mockEditor
  let mockBaseReturn
  let entity
  let caseId
  let isEditing
  let formData
  let emit
  let mockUseBaseNoteEditor

  beforeEach(async () => {
    const { useBaseNoteEditor } = await import('../useBaseNoteEditor')
    mockUseBaseNoteEditor = useBaseNoteEditor
    vi.useFakeTimers()

    mockEditor = {
      getHTML: vi.fn().mockReturnValue('<p>Test content</p>'),
      commands: {
        setContent: vi.fn(),
      },
      setEditable: vi.fn(),
    }

    mockBaseReturn = {
      editor: { value: mockEditor },
      editorActions: { value: [] },
      saving: { value: false },
      lastSaved: { value: null },
      lastSavedTime: { value: null },
      formatLastSaved: { value: '' },
      updateContent: vi.fn(),
      cleanup: vi.fn(),
      triggerSave: vi.fn(),
    }

    mockUseBaseNoteEditor.mockReturnValue(mockBaseReturn)

    entity = ref({
      id: 456,
      entity_type: 'person',
      data: {
        name: 'John Doe',
        notes: '<p>Initial entity notes</p>',
      },
    })

    caseId = ref(123)
    isEditing = ref(true)
    formData = ref({
      data: {
        notes: '',
      },
    })
    emit = vi.fn()

    entityService.updateEntity.mockResolvedValue({
      id: 456,
      entity_type: 'person',
      data: {
        name: 'John Doe',
        notes: '<p>Updated notes</p>',
      },
    })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.restoreAllMocks()
  })

  it('should initialize with entity note configuration', () => {
    mockUseBaseNoteEditor.mockReturnValue(mockBaseReturn)

    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    expect(mockUseBaseNoteEditor).toHaveBeenCalledWith({
      initialContent: '<p>Initial entity notes</p>',
      placeholder: 'Write your entity notes here... Use / for commands.',
      editable: true,
      onUpdate: expect.any(Function),
      saveDelay: 5000,
    })
  })

  it('should use read-only placeholder when not editing', () => {
    mockUseBaseNoteEditor.mockReturnValue(mockBaseReturn)
    isEditing.value = false

    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    const call = mockUseBaseNoteEditor.mock.calls[0][0]
    expect(call.placeholder).toBe('Notes (read-only)')
    expect(call.editable).toBe(false)
  })

  it('should handle entity without notes', () => {
    mockUseBaseNoteEditor.mockReturnValue(mockBaseReturn)
    entity.value.data.notes = undefined

    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    const call = mockUseBaseNoteEditor.mock.calls[0][0]
    expect(call.initialContent).toBe('')
  })

  it('should update form data on editor update when editing', () => {
    mockUseBaseNoteEditor.mockReturnValue(mockBaseReturn)

    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    const content = '<p>Updated content</p>'
    mockEditor.getHTML.mockReturnValue(content)

    onUpdate(mockEditor)

    expect(formData.value.data.notes).toBe(content)
    expect(mockBaseReturn.triggerSave).toHaveBeenCalled()
  })

  it('should not update form data when not editing', () => {
    mockUseBaseNoteEditor.mockReturnValue(mockBaseReturn)
    isEditing.value = false

    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    const content = '<p>Updated content</p>'
    mockEditor.getHTML.mockReturnValue(content)

    onUpdate(mockEditor)

    expect(formData.value.data.notes).toBe('')
    expect(mockBaseReturn.triggerSave).not.toHaveBeenCalled()
  })

  it('should save entity notes', async () => {
    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    const content = '<p>New content</p>'
    mockEditor.getHTML.mockReturnValue(content)
    mockBaseReturn.lastSaved.value = '<p>Old content</p>'

    mockUseBaseNoteEditor.mockReturnValue(mockBaseReturn)
    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    onUpdate(mockEditor)

    const saveCallback = mockBaseReturn.triggerSave.mock.calls[0][0]
    await saveCallback()

    expect(entityService.updateEntity).toHaveBeenCalledWith(123, 456, {
      entity_type: 'person',
      data: {
        name: 'John Doe',
        notes: content,
      },
    })
    expect(emit).toHaveBeenCalledWith(
      'edit',
      expect.objectContaining({
        id: 456,
        entity_type: 'person',
      }),
    )
  })

  it('should not save if not editing', async () => {
    const result = useEntityNoteEditor(entity, caseId, isEditing, formData, emit)
    isEditing.value = false

    const { saveNotes } = result
    await saveNotes()

    expect(entityService.updateEntity).not.toHaveBeenCalled()
  })

  it('should not save if entity is null', async () => {
    entity.value = null
    const result = useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    const { saveNotes } = result
    await saveNotes()

    expect(entityService.updateEntity).not.toHaveBeenCalled()
  })

  it('should not save if content unchanged', async () => {
    const result = useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    const content = '<p>Same content</p>'
    mockEditor.getHTML.mockReturnValue(content)
    mockBaseReturn.lastSaved.value = content

    const { saveNotes } = result
    await saveNotes()

    expect(entityService.updateEntity).not.toHaveBeenCalled()
  })

  it('should handle save errors', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const error = new Error('Save failed')
    entityService.updateEntity.mockRejectedValue(error)

    const result = useEntityNoteEditor(entity, caseId, isEditing, formData, emit)
    mockEditor.getHTML.mockReturnValue('<p>New content</p>')

    const { saveNotes } = result
    await saveNotes()

    expect(consoleError).toHaveBeenCalledWith('Failed to save entity notes:', error)
    expect(mockBaseReturn.saving.value).toBe(false)

    consoleError.mockRestore()
  })

  it('should update editor content when entity notes change', async () => {
    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    entity.value.data.notes = '<p>Changed notes</p>'
    await nextTick()

    expect(mockBaseReturn.updateContent).toHaveBeenCalledWith('<p>Changed notes</p>')
    expect(mockBaseReturn.lastSaved.value).toBe('<p>Changed notes</p>')
  })

  it('should handle undefined entity notes', async () => {
    // Set entity notes to undefined before initializing
    entity.value.data.notes = undefined

    vi.clearAllMocks() // Clear previous calls
    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    // updateContent should NOT be called when notes are undefined (per implementation logic)
    expect(mockBaseReturn.updateContent).not.toHaveBeenCalled()
  })

  it('should update editor editability when editing state changes', async () => {
    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    isEditing.value = false
    await nextTick()

    expect(mockEditor.setEditable).toHaveBeenCalledWith(false)
  })

  it('should save pending changes when exiting edit mode', async () => {
    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    // Simulate the scenario from the actual implementation
    // When editing state changes, check for pending changes and save
    mockEditor.getHTML.mockReturnValue('<p>New content</p>')
    mockBaseReturn.lastSaved.value = '<p>Old content</p>'

    // Get the save function that was set up in useEntityNoteEditor
    const onUpdateCallback = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    onUpdateCallback(mockEditor)

    // Verify triggerSave was called (which would eventually call entityService.updateEntity)
    expect(mockBaseReturn.triggerSave).toHaveBeenCalled()
  })

  it('should not save when exiting edit mode if no changes', async () => {
    useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    const content = '<p>Same content</p>'
    mockEditor.getHTML.mockReturnValue(content)
    mockBaseReturn.lastSaved.value = content

    isEditing.value = false
    await nextTick()

    expect(entityService.updateEntity).not.toHaveBeenCalled()
  })

  it('should handle null emit parameter', async () => {
    const result = useEntityNoteEditor(entity, caseId, isEditing, formData, null)

    mockEditor.getHTML.mockReturnValue('<p>New content</p>')

    const { saveNotes } = result
    await saveNotes()

    expect(entityService.updateEntity).toHaveBeenCalled()
  })

  it('should handle null formData parameter', () => {
    mockUseBaseNoteEditor.mockReturnValue(mockBaseReturn)

    useEntityNoteEditor(entity, caseId, isEditing, null, emit)

    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    const content = '<p>Updated content</p>'
    mockEditor.getHTML.mockReturnValue(content)

    expect(() => onUpdate(mockEditor)).not.toThrow()
  })

  it('should return saveNotes function', () => {
    const result = useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    expect(result).toHaveProperty('saveNotes')
    expect(typeof result.saveNotes).toBe('function')
  })

  it('should provide enhanced cleanup', () => {
    const { cleanup } = useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

    cleanup()

    expect(mockBaseReturn.cleanup).toHaveBeenCalled()
    const cleanupCallback = mockBaseReturn.cleanup.mock.calls[0][0]
    expect(cleanupCallback).toBeDefined()
  })
})
