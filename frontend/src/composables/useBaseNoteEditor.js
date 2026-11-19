import { useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Highlight from '@tiptap/extension-highlight'
import { TaskList, TaskItem } from '@tiptap/extension-list'
import { Placeholder } from '@tiptap/extensions'
import { ref, computed, onBeforeUnmount, onMounted } from 'vue'

const relativeTime = new Intl.RelativeTimeFormat('en', { numeric: 'always' })
const RELATIVE_UNITS = [
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
]

const formatTimeAgo = (date) => {
  const seconds = Math.max(0, Math.round((Date.now() - date) / 1000))
  const [unit, size] = RELATIVE_UNITS.find(([, size]) => seconds >= size) ?? ['second', 1]
  // Negative zero keeps "0 seconds ago" instead of "in 0 seconds".
  return relativeTime.format(-Math.floor(seconds / size), unit)
}

// [icon, title, chain command, active mark]
const TOOLBAR_ACTIONS = [
  ['mdi-format-bold', 'Bold (Ctrl+B)', 'toggleBold', 'bold'],
  ['mdi-format-italic', 'Italic (Ctrl+I)', 'toggleItalic', 'italic'],
  ['mdi-format-underline', 'Underline (Ctrl+U)', 'toggleUnderline', 'underline'],
  ['mdi-format-strikethrough', 'Strikethrough', 'toggleStrike', 'strike'],
  ['mdi-marker', 'Highlight', 'toggleHighlight', 'highlight'],
  ['mdi-format-list-bulleted', 'Bullet List', 'toggleBulletList', 'bulletList'],
  ['mdi-format-list-numbered', 'Ordered List', 'toggleOrderedList', 'orderedList'],
  ['mdi-format-list-checks', 'Task List', 'toggleTaskList', 'taskList'],
  ['mdi-format-quote-close', 'Blockquote', 'toggleBlockquote', 'blockquote'],
]

export function useBaseNoteEditor({
  initialContent = '',
  placeholder = 'Write your notes here... Use / for commands.',
  editable = true,
  label = 'Notes',
  onUpdate = null,
  onExit = null,
  saveDelay = 1000,
}) {
  const lastSaved = ref(null)
  const lastSavedTime = ref(null)
  const saving = ref(false)

  const formatLastSaved = computed(() => {
    if (!lastSavedTime.value) return ''
    return formatTimeAgo(lastSavedTime.value)
  })

  let saveTimeout
  const cancelPendingSave = () => clearTimeout(saveTimeout)
  const triggerSave = (saveCallback) => {
    clearTimeout(saveTimeout)
    if (saveCallback) {
      saveTimeout = setTimeout(saveCallback, saveDelay)
    }
  }

  // Capture pending notes before Tiptap's own unmount hook destroys the editor.
  onBeforeUnmount(() => cleanup(onExit))

  const editor = useEditor({
    content: initialContent,
    editable,
    extensions: [
      StarterKit.configure({
        // Preserve v2 editing behavior without the new v3 defaults.
        trailingNode: false,
        listKeymap: false,
      }),
      Highlight.configure({
        multicolor: true,
      }),
      TaskList.configure({
        HTMLAttributes: {
          class: 'task-list',
        },
      }),
      TaskItem.configure({
        nested: true,
        HTMLAttributes: {
          class: 'task-item',
        },
      }),
      Placeholder.configure({
        placeholder: ({ node }) => {
          if (node.type.name === 'heading') {
            return "What's the title?"
          }
          return placeholder
        },
      }),
    ],
    shouldRerenderOnTransaction: true,
    onUpdate: ({ editor }) => {
      if (onUpdate) {
        onUpdate(editor)
      }
    },
    editorProps: {
      attributes: {
        class: 'tiptap-editor',
        role: 'textbox',
        'aria-label': label,
        'aria-multiline': 'true',
        style: 'min-height: 150px;',
      },
    },
  })

  const editorActions = TOOLBAR_ACTIONS.map(([icon, title, command, mark]) => ({
    icon,
    title,
    action: () => editor.value?.chain().focus()[command]().run(),
    isActive: () => editor.value?.isActive(mark),
  }))

  onMounted(() => {
    lastSaved.value = editor.value.getHTML()
  })

  const updateContent = (newVal) => {
    const currentContent = editor.value?.getHTML()
    if (newVal !== currentContent && editor.value) {
      editor.value.commands.setContent(newVal || '', { emitUpdate: false })
      lastSaved.value = editor.value.getHTML()
    }
  }

  const cleanup = (saveCallback) => {
    clearTimeout(saveTimeout)
    if (editor.value && !editor.value.isDestroyed) {
      const content = editor.value.getHTML()
      if ((content !== lastSaved.value || saving.value) && saveCallback) {
        saveCallback()
      }
      editor.value.destroy()
    }
  }

  return {
    editor,
    editorActions,
    saving,
    lastSaved,
    lastSavedTime,
    formatLastSaved,
    updateContent,
    cleanup,
    cancelPendingSave,
    triggerSave,
  }
}
