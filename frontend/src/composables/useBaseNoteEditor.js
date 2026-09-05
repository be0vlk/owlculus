import { useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Highlight from '@tiptap/extension-highlight'
import { TaskList, TaskItem } from '@tiptap/extension-list'
import { Placeholder } from '@tiptap/extensions'
import { ref, computed, onBeforeUnmount } from 'vue'
import { formatDistanceToNow } from 'date-fns'

export function useBaseNoteEditor({
  initialContent = '',
  placeholder = 'Write your notes here... Use / for commands.',
  editable = true,
  label = 'Notes',
  onUpdate = null,
  saveDelay = 1000,
}) {
  const lastSaved = ref(null)
  const lastSavedTime = ref(null)
  const saving = ref(false)

  const formatLastSaved = computed(() => {
    if (!lastSavedTime.value) return ''
    return formatDistanceToNow(lastSavedTime.value, { addSuffix: true })
  })

  let saveTimeout
  const triggerSave = (saveCallback) => {
    clearTimeout(saveTimeout)
    if (saveCallback) {
      saveTimeout = setTimeout(saveCallback, saveDelay)
    }
  }

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

  const editorActions = computed(() => [
    {
      icon: 'mdi-format-bold',
      title: 'Bold (Ctrl+B)',
      action: () => editor.value?.chain().focus().toggleBold().run(),
      isActive: () => editor.value?.isActive('bold'),
    },
    {
      icon: 'mdi-format-italic',
      title: 'Italic (Ctrl+I)',
      action: () => editor.value?.chain().focus().toggleItalic().run(),
      isActive: () => editor.value?.isActive('italic'),
    },
    {
      icon: 'mdi-format-underline',
      title: 'Underline (Ctrl+U)',
      action: () => editor.value?.chain().focus().toggleUnderline().run(),
      isActive: () => editor.value?.isActive('underline'),
    },
    {
      icon: 'mdi-format-strikethrough',
      title: 'Strikethrough',
      action: () => editor.value?.chain().focus().toggleStrike().run(),
      isActive: () => editor.value?.isActive('strike'),
    },
    {
      icon: 'mdi-marker',
      title: 'Highlight',
      action: () => editor.value?.chain().focus().toggleHighlight().run(),
      isActive: () => editor.value?.isActive('highlight'),
    },
    {
      icon: 'mdi-format-list-bulleted',
      title: 'Bullet List',
      action: () => editor.value?.chain().focus().toggleBulletList().run(),
      isActive: () => editor.value?.isActive('bulletList'),
    },
    {
      icon: 'mdi-format-list-numbered',
      title: 'Ordered List',
      action: () => editor.value?.chain().focus().toggleOrderedList().run(),
      isActive: () => editor.value?.isActive('orderedList'),
    },
    {
      icon: 'mdi-format-list-checks',
      title: 'Task List',
      action: () => editor.value?.chain().focus().toggleTaskList().run(),
      isActive: () => editor.value?.isActive('taskList'),
    },
    {
      icon: 'mdi-format-quote-close',
      title: 'Blockquote',
      action: () => editor.value?.chain().focus().toggleBlockquote().run(),
      isActive: () => editor.value?.isActive('blockquote'),
    },
  ])

  const updateContent = (newVal) => {
    const currentContent = editor.value?.getHTML()
    if (newVal !== currentContent && editor.value) {
      editor.value.commands.setContent(newVal || '', { emitUpdate: false })
    }
  }

  const cleanup = (saveCallback) => {
    clearTimeout(saveTimeout)
    if (editor.value && !editor.value.isDestroyed) {
      const content = editor.value.getHTML()
      if (content !== lastSaved.value && saveCallback) {
        saveCallback()
      }
      editor.value.destroy()
    }
  }

  onBeforeUnmount(() => cleanup())

  return {
    editor,
    editorActions,
    saving,
    lastSaved,
    lastSavedTime,
    formatLastSaved,
    updateContent,
    cleanup,
    triggerSave,
  }
}
