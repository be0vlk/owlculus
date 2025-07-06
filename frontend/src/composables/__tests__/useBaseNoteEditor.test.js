import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useBaseNoteEditor } from '../useBaseNoteEditor'
import { useEditor } from '@tiptap/vue-3'

vi.mock('@tiptap/vue-3', () => ({
  useEditor: vi.fn(),
}))

describe('useBaseNoteEditor', () => {
  let mockEditor
  let updateCallback

  beforeEach(() => {
    vi.useFakeTimers()

    mockEditor = {
      commands: {
        setContent: vi.fn(),
      },
      getHTML: vi.fn().mockReturnValue('<p>Test content</p>'),
      chain: vi.fn().mockReturnThis(),
      focus: vi.fn().mockReturnThis(),
      toggleBold: vi.fn().mockReturnThis(),
      toggleItalic: vi.fn().mockReturnThis(),
      toggleUnderline: vi.fn().mockReturnThis(),
      toggleStrike: vi.fn().mockReturnThis(),
      toggleHighlight: vi.fn().mockReturnThis(),
      toggleBulletList: vi.fn().mockReturnThis(),
      toggleOrderedList: vi.fn().mockReturnThis(),
      toggleTaskList: vi.fn().mockReturnThis(),
      toggleBlockquote: vi.fn().mockReturnThis(),
      run: vi.fn().mockReturnThis(),
      isActive: vi.fn().mockReturnValue(false),
      destroy: vi.fn(),
      setEditable: vi.fn(),
    }

    useEditor.mockImplementation((config) => {
      updateCallback = config.onUpdate
      return { value: mockEditor }
    })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.restoreAllMocks()
  })

  it('should initialize with default values', () => {
    const result = useBaseNoteEditor({})

    expect(result.editor.value).toBe(mockEditor)
    expect(result.saving.value).toBe(false)
    expect(result.lastSaved.value).toBeNull()
    expect(result.lastSavedTime.value).toBeNull()
    expect(result.formatLastSaved.value).toBe('')
  })

  it('should create editor with provided initial content', () => {
    const initialContent = '<p>Initial content</p>'

    useBaseNoteEditor({ initialContent })

    const editorConfig = useEditor.mock.calls[0][0]
    expect(editorConfig.content).toBe(initialContent)
  })

  it('should set custom placeholder', () => {
    const customPlaceholder = 'Custom placeholder'

    useBaseNoteEditor({ placeholder: customPlaceholder })

    const editorConfig = useEditor.mock.calls[0][0]
    const placeholderExtension = editorConfig.extensions.find((ext) => ext.name === 'placeholder')
    expect(placeholderExtension).toBeDefined()
  })

  it('should handle editor updates', () => {
    const onUpdate = vi.fn()

    useBaseNoteEditor({ onUpdate })

    // Simulate editor update
    updateCallback({ editor: mockEditor })

    expect(onUpdate).toHaveBeenCalledWith(mockEditor)
  })

  it('should trigger save with delay', () => {
    const saveCallback = vi.fn()
    const result = useBaseNoteEditor({ saveDelay: 500 })

    result.triggerSave(saveCallback)

    expect(saveCallback).not.toHaveBeenCalled()

    vi.advanceTimersByTime(500)

    expect(saveCallback).toHaveBeenCalled()
  })

  it('should cancel previous save when triggering new one', () => {
    const saveCallback1 = vi.fn()
    const saveCallback2 = vi.fn()
    const result = useBaseNoteEditor({ saveDelay: 500 })

    result.triggerSave(saveCallback1)
    vi.advanceTimersByTime(200)

    result.triggerSave(saveCallback2)
    vi.advanceTimersByTime(500)

    expect(saveCallback1).not.toHaveBeenCalled()
    expect(saveCallback2).toHaveBeenCalled()
  })

  it('should provide editor actions', () => {
    const result = useBaseNoteEditor({})

    expect(result.editorActions.value).toHaveLength(9)

    const boldAction = result.editorActions.value.find((a) => a.icon === 'mdi-format-bold')
    expect(boldAction).toBeDefined()
    expect(boldAction.title).toBe('Bold (Ctrl+B)')

    boldAction.action()
    expect(mockEditor.chain).toHaveBeenCalled()
    expect(mockEditor.toggleBold).toHaveBeenCalled()

    const isActive = boldAction.isActive()
    expect(mockEditor.isActive).toHaveBeenCalledWith('bold')
    expect(isActive).toBe(false)
  })

  it('should update content when different from current', () => {
    const result = useBaseNoteEditor({})

    const newContent = '<p>New content</p>'
    mockEditor.getHTML.mockReturnValue('<p>Old content</p>')

    result.updateContent(newContent)

    expect(mockEditor.commands.setContent).toHaveBeenCalledWith(newContent, false)
  })

  it('should not update content when same as current', () => {
    const result = useBaseNoteEditor({})

    const sameContent = '<p>Same content</p>'
    mockEditor.getHTML.mockReturnValue(sameContent)

    result.updateContent(sameContent)

    expect(mockEditor.commands.setContent).not.toHaveBeenCalled()
  })

  it('should handle null content in updateContent', () => {
    const result = useBaseNoteEditor({})

    mockEditor.getHTML.mockReturnValue('<p>Current content</p>')

    result.updateContent(null)

    expect(mockEditor.commands.setContent).toHaveBeenCalledWith('', false)
  })

  it('should cleanup on unmount', () => {
    const saveCallback = vi.fn()
    const result = useBaseNoteEditor({})

    result.lastSaved.value = '<p>Old content</p>'
    mockEditor.getHTML.mockReturnValue('<p>New content</p>')

    result.cleanup(saveCallback)

    expect(saveCallback).toHaveBeenCalled()
    expect(mockEditor.destroy).toHaveBeenCalled()
  })

  it('should not call save on cleanup if content unchanged', () => {
    const saveCallback = vi.fn()
    const result = useBaseNoteEditor({})

    const content = '<p>Same content</p>'
    result.lastSaved.value = content
    mockEditor.getHTML.mockReturnValue(content)

    result.cleanup(saveCallback)

    expect(saveCallback).not.toHaveBeenCalled()
    expect(mockEditor.destroy).toHaveBeenCalled()
  })

  it('should format last saved time', () => {
    const result = useBaseNoteEditor({})

    expect(result.formatLastSaved.value).toBe('')

    result.lastSavedTime.value = new Date()

    expect(result.formatLastSaved.value).toMatch(/ago$/)
  })
})
