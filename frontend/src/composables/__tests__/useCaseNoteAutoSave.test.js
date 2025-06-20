import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useCaseNoteAutoSave } from '../useCaseNoteAutoSave'
import { caseService } from '../../services/case'
import { nextTick } from 'vue'

vi.mock('../../services/case', () => ({
  caseService: {
    updateCase: vi.fn(),
  },
}))

const mockUseBaseNoteEditor = vi.fn()
vi.mock('../useBaseNoteEditor', () => ({
  useBaseNoteEditor: mockUseBaseNoteEditor,
}))

describe('useCaseNoteAutoSave', () => {
  let mockEditor
  let mockBaseReturn
  let props
  let emit

  beforeEach(() => {
    vi.useFakeTimers()

    mockEditor = {
      getHTML: vi.fn().mockReturnValue('<p>Test content</p>'),
      commands: {
        setContent: vi.fn(),
      },
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

    caseService.updateCase.mockResolvedValue({})
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.restoreAllMocks()
  })

  it('should initialize with case note configuration', () => {
    // Already mocked

    useCaseNoteAutoSave(props, emit)

    expect(mockUseBaseNoteEditor).toHaveBeenCalledWith({
      initialContent: '<p>Initial content</p>',
      placeholder: 'Write your case notes here... Use / for commands.',
      editable: true,
      onUpdate: expect.any(Function),
      saveDelay: 1000,
    })
  })

  it('should handle empty modelValue', () => {
    // Already mocked
    props.modelValue = undefined

    useCaseNoteAutoSave(props, emit)

    const call = mockUseBaseNoteEditor.mock.calls[0][0]
    expect(call.initialContent).toBe('')
  })

  it('should emit update:modelValue on editor update', () => {
    // Already mocked

    useCaseNoteAutoSave(props, emit)

    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    const content = '<p>Updated content</p>'
    mockEditor.getHTML.mockReturnValue(content)

    onUpdate(mockEditor)

    expect(emit).toHaveBeenCalledWith('update:modelValue', content)
    expect(mockBaseReturn.triggerSave).toHaveBeenCalled()
  })

  it('should save notes to case service', async () => {
    const result = useCaseNoteAutoSave(props, emit)

    const content = '<p>New content</p>'
    mockEditor.getHTML.mockReturnValue(content)
    mockBaseReturn.lastSaved.value = '<p>Old content</p>'
    mockBaseReturn.saving.value = false

    // Already mocked
    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    onUpdate(mockEditor)

    const saveCallback = mockBaseReturn.triggerSave.mock.calls[0][0]
    await saveCallback()

    expect(caseService.updateCase).toHaveBeenCalledWith(123, { notes: content })
    expect(mockBaseReturn.lastSaved.value).toBe(content)
    expect(mockBaseReturn.lastSavedTime.value).toBeInstanceOf(Date)
  })

  it('should not save if content unchanged', async () => {
    const result = useCaseNoteAutoSave(props, emit)

    const content = '<p>Same content</p>'
    mockEditor.getHTML.mockReturnValue(content)
    mockBaseReturn.lastSaved.value = content

    // Already mocked
    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    onUpdate(mockEditor)

    const saveCallback = mockBaseReturn.triggerSave.mock.calls[0][0]
    await saveCallback()

    expect(caseService.updateCase).not.toHaveBeenCalled()
  })

  it('should not save if editor is null', async () => {
    const result = useCaseNoteAutoSave(props, emit)
    mockBaseReturn.editor.value = null

    // Already mocked
    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    onUpdate(mockEditor)

    const saveCallback = mockBaseReturn.triggerSave.mock.calls[0][0]
    await saveCallback()

    expect(caseService.updateCase).not.toHaveBeenCalled()
  })

  it('should handle save errors', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const error = new Error('Save failed')
    caseService.updateCase.mockRejectedValue(error)

    const result = useCaseNoteAutoSave(props, emit)
    mockEditor.getHTML.mockReturnValue('<p>New content</p>')

    // Already mocked
    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    onUpdate(mockEditor)

    const saveCallback = mockBaseReturn.triggerSave.mock.calls[0][0]
    await saveCallback()

    expect(consoleError).toHaveBeenCalledWith('Failed to save notes:', error)
    expect(mockBaseReturn.saving.value).toBe(false)

    consoleError.mockRestore()
  })

  it('should update content when modelValue changes', async () => {
    const { updateContent } = useCaseNoteAutoSave(props, emit)

    expect(updateContent).toBe(mockBaseReturn.updateContent)
  })

  it('should provide enhanced cleanup that saves on cleanup', () => {
    const { cleanup } = useCaseNoteAutoSave(props, emit)

    cleanup()

    expect(mockBaseReturn.cleanup).toHaveBeenCalled()
    const cleanupCallback = mockBaseReturn.cleanup.mock.calls[0][0]
    expect(cleanupCallback).toBeDefined()
  })

  it('should return all necessary properties', () => {
    const result = useCaseNoteAutoSave(props, emit)

    expect(result).toEqual({
      editor: mockBaseReturn.editor,
      editorActions: mockBaseReturn.editorActions,
      saving: mockBaseReturn.saving,
      lastSavedTime: mockBaseReturn.lastSavedTime,
      formatLastSaved: mockBaseReturn.formatLastSaved,
      updateContent: mockBaseReturn.updateContent,
      cleanup: expect.any(Function),
    })
  })

  it('should handle saving state correctly', async () => {
    const result = useCaseNoteAutoSave(props, emit)

    mockEditor.getHTML.mockReturnValue('<p>New content</p>')
    mockBaseReturn.saving.value = false

    // Already mocked
    const onUpdate = mockUseBaseNoteEditor.mock.calls[0][0].onUpdate
    onUpdate(mockEditor)

    const saveCallback = mockBaseReturn.triggerSave.mock.calls[0][0]
    const savePromise = saveCallback()

    expect(mockBaseReturn.saving.value).toBe(true)

    await savePromise

    expect(mockBaseReturn.saving.value).toBe(false)
  })
})
