import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { useBaseNoteEditor } from '../useBaseNoteEditor'
import { useEditor } from '@tiptap/vue-3'

vi.mock('@tiptap/vue-3', () => ({
  useEditor: vi.fn(),
}))

vi.mock('vue', async () => {
  const actual = await vi.importActual('vue')
  return {
    ...actual,
    onBeforeUnmount: vi.fn((cb) => {
      // Store the cleanup callback for manual testing
      if (global.testCleanupCallback) {
        global.testCleanupCallback = cb
      }
    }),
  }
})

describe('useBaseNoteEditor', () => {
  let mockEditor
  let updateCallback

  beforeEach(() => {
    vi.useFakeTimers()
    global.testCleanupCallback = null

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
    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({})
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)

    expect(wrapper.vm.editor.value).toBe(mockEditor)
    expect(wrapper.vm.saving.value).toBe(false)
    expect(wrapper.vm.lastSaved.value).toBeNull()
    expect(wrapper.vm.lastSavedTime.value).toBeNull()
    expect(wrapper.vm.formatLastSaved.value).toBe('')

    wrapper.unmount()
  })

  it('should create editor with provided initial content', () => {
    const initialContent = '<p>Initial content</p>'

    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({ initialContent })
      },
      template: '<div />',
    })

    mount(TestComponent)

    const editorConfig = useEditor.mock.calls[0][0]
    expect(editorConfig.content).toBe(initialContent)
  })

  it('should set custom placeholder', () => {
    const placeholder = 'Custom placeholder text'

    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({ placeholder })
      },
      template: '<div />',
    })

    mount(TestComponent)

    const editorConfig = useEditor.mock.calls[0][0]
    const placeholderExtension = editorConfig.extensions.find((ext) => ext.options?.placeholder)

    expect(placeholderExtension).toBeDefined()
    const placeholderFn = placeholderExtension.options.placeholder
    expect(placeholderFn({ node: { type: { name: 'paragraph' } } })).toBe(placeholder)
    expect(placeholderFn({ node: { type: { name: 'heading' } } })).toBe("What's the title?")
  })

  it('should handle editor updates', () => {
    const onUpdate = vi.fn()

    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({ onUpdate })
      },
      template: '<div />',
    })

    mount(TestComponent)

    updateCallback({ editor: mockEditor })

    expect(onUpdate).toHaveBeenCalledWith(mockEditor)
  })

  it('should trigger save with delay', () => {
    const saveCallback = vi.fn()
    const saveDelay = 2000

    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({ saveDelay })
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    const { triggerSave } = wrapper.vm

    triggerSave(saveCallback)

    expect(saveCallback).not.toHaveBeenCalled()

    vi.advanceTimersByTime(saveDelay)

    expect(saveCallback).toHaveBeenCalledTimes(1)
  })

  it('should cancel previous save when triggering new one', () => {
    const saveCallback = vi.fn()
    const saveDelay = 2000

    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({ saveDelay })
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    const { triggerSave } = wrapper.vm

    triggerSave(saveCallback)
    vi.advanceTimersByTime(1000)

    triggerSave(saveCallback)
    vi.advanceTimersByTime(1500)

    expect(saveCallback).not.toHaveBeenCalled()

    vi.advanceTimersByTime(500)

    expect(saveCallback).toHaveBeenCalledTimes(1)
  })

  it('should provide editor actions', () => {
    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({})
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    const { editorActions } = wrapper.vm

    expect(editorActions.value).toHaveLength(9)

    const boldAction = editorActions.value.find((a) => a.icon === 'mdi-format-bold')
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
    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({})
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    const { updateContent } = wrapper.vm

    const newContent = '<p>New content</p>'
    mockEditor.getHTML.mockReturnValue('<p>Old content</p>')

    updateContent(newContent)

    expect(mockEditor.commands.setContent).toHaveBeenCalledWith(newContent, false)
  })

  it('should not update content when same as current', () => {
    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({})
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    const { updateContent } = wrapper.vm

    const content = '<p>Same content</p>'
    mockEditor.getHTML.mockReturnValue(content)

    updateContent(content)

    expect(mockEditor.commands.setContent).not.toHaveBeenCalled()
  })

  it('should handle null content in updateContent', () => {
    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({})
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    const { updateContent } = wrapper.vm

    mockEditor.getHTML.mockReturnValue('<p>Content</p>')

    updateContent(null)

    expect(mockEditor.commands.setContent).toHaveBeenCalledWith('', false)
  })

  it('should cleanup on unmount', () => {
    const saveCallback = vi.fn()

    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({})
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    const { cleanup, lastSaved } = wrapper.vm

    lastSaved.value.value = '<p>Old content</p>'
    mockEditor.getHTML.mockReturnValue('<p>New content</p>')

    cleanup(saveCallback)

    expect(saveCallback).toHaveBeenCalled()
    expect(mockEditor.destroy).toHaveBeenCalled()
  })

  it('should not call save on cleanup if content unchanged', () => {
    const saveCallback = vi.fn()

    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({})
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    const { cleanup, lastSaved } = wrapper.vm

    const content = '<p>Same content</p>'
    lastSaved.value.value = content
    mockEditor.getHTML.mockReturnValue(content)

    cleanup(saveCallback)

    expect(saveCallback).not.toHaveBeenCalled()
    expect(mockEditor.destroy).toHaveBeenCalled()
  })

  it('should format last saved time', async () => {
    const TestComponent = defineComponent({
      setup() {
        return useBaseNoteEditor({})
      },
      template: '<div />',
    })

    const wrapper = mount(TestComponent)
    const { formatLastSaved, lastSavedTime } = wrapper.vm

    expect(formatLastSaved.value).toBe('')

    lastSavedTime.value.value = new Date()
    await nextTick()

    expect(formatLastSaved.value).toMatch(/ago$/)
  })
})
