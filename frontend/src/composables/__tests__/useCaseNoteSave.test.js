import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useCaseNoteSave } from '../useCaseNoteSave'
import { caseService } from '../../services/case'

vi.mock('../../services/case', () => ({
  caseService: {
    updateCase: vi.fn(),
  },
}))

vi.mock('../useBaseNoteEditor', () => ({
  useBaseNoteEditor: vi.fn(),
}))

describe('useCaseNoteSave', () => {
  let mockEditor
  let mockBaseReturn
  let props
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

    props = {
      modelValue: '<p>Initial content</p>',
      caseId: 123,
    }

    emit = vi.fn()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('auto-save mode', () => {
    it('sets up base editor with correct configuration', () => {
      useCaseNoteSave(props, emit, { saveMode: 'auto' })

      expect(mockUseBaseNoteEditor).toHaveBeenCalledWith({
        initialContent: props.modelValue,
        placeholder: 'Write your case notes here... Use / for commands.',
        editable: true,
        onUpdate: expect.any(Function),
        saveDelay: 1000,
      })
    })

    it('triggers save on editor update in auto mode', () => {
      useCaseNoteSave(props, emit, { saveMode: 'auto' })

      const onUpdateCallback = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
      onUpdateCallback(mockEditor)

      expect(emit).toHaveBeenCalledWith('update:modelValue', '<p>Test content</p>')
      expect(mockBaseReturn.triggerSave).toHaveBeenCalled()
    })

    it('saves notes to case service when save is triggered', async () => {
      caseService.updateCase.mockResolvedValue({})
      useCaseNoteSave(props, emit, { saveMode: 'auto' })

      // Trigger the onUpdate callback which should call triggerSave with saveNotes function
      const onUpdateCallback = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
      onUpdateCallback(mockEditor)

      // Get the save function that was passed to triggerSave
      const saveNotes = mockBaseReturn.triggerSave.mock.calls[0][0]
      await saveNotes()

      expect(caseService.updateCase).toHaveBeenCalledWith(123, {
        notes: '<p>Test content</p>',
      })
    })

    it('includes save in cleanup for auto mode', () => {
      const result = useCaseNoteSave(props, emit, { saveMode: 'auto' })

      result.cleanup()

      expect(mockBaseReturn.cleanup).toHaveBeenCalledWith(expect.any(Function))
    })
  })

  describe('manual save mode', () => {
    it('does not trigger save on editor update in manual mode', () => {
      useCaseNoteSave(props, emit, { saveMode: 'manual' })

      const onUpdateCallback = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
      onUpdateCallback(mockEditor)

      expect(emit).toHaveBeenCalledWith('update:modelValue', '<p>Test content</p>')
      expect(mockBaseReturn.triggerSave).not.toHaveBeenCalled()
    })

    it('does not include save in cleanup for manual mode', () => {
      const result = useCaseNoteSave(props, emit, { saveMode: 'manual' })

      result.cleanup()

      expect(mockBaseReturn.cleanup).toHaveBeenCalledWith()
    })
  })

  describe('read-only mode', () => {
    it('sets placeholder for read-only mode', () => {
      props.isEditing = false
      useCaseNoteSave(props, emit, { saveMode: 'manual' })

      expect(mockUseBaseNoteEditor).toHaveBeenCalledWith({
        initialContent: props.modelValue,
        placeholder: 'Notes (read-only)',
        editable: false,
        onUpdate: expect.any(Function),
        saveDelay: null,
      })
    })

    it('updates editor editability when isEditing changes', () => {
      props.isEditing = true
      useCaseNoteSave(props, emit, { saveMode: 'manual' })

      // Simulate the watch callback
      mockEditor.setEditable(false)

      expect(mockEditor.setEditable).toHaveBeenCalledWith(false)
    })
  })

  describe('content updates', () => {
    it('returns expected composable properties', () => {
      const result = useCaseNoteSave(props, emit, { saveMode: 'auto' })

      expect(result).toHaveProperty('editor')
      expect(result).toHaveProperty('editorActions')
      expect(result).toHaveProperty('saving')
      expect(result).toHaveProperty('lastSavedTime')
      expect(result).toHaveProperty('formatLastSaved')
      expect(result).toHaveProperty('updateContent')
      expect(result).toHaveProperty('cleanup')
    })
  })
})
