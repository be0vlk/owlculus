import { useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'
import Highlight from '@tiptap/extension-highlight'
import TaskList from '@tiptap/extension-task-list'
import TaskItem from '@tiptap/extension-task-item'
import Placeholder from '@tiptap/extension-placeholder'
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { entityService } from '../services/entity'
import { formatDistanceToNow } from 'date-fns'

export function useEntityNoteEditor(entity, caseId, isEditing, formData, emit) {
  const lastSaved = ref(null)
  const lastSavedTime = ref(null)
  const saving = ref(false)

  const formatLastSaved = computed(() => {
    if (!lastSavedTime.value) return ''
    return formatDistanceToNow(lastSavedTime.value, { addSuffix: true })
  })

  const saveNotes = async () => {
    if (!editor.value || !entity.value || !isEditing.value) return

    const content = editor.value.getHTML()
    if (content === lastSaved.value) return

    try {
      saving.value = true

      const updatedEntity = await entityService.updateEntity(caseId.value, entity.value.id, {
        entity_type: entity.value.entity_type,
        data: {
          ...entity.value.data,
          notes: content,
        },
      })

      lastSaved.value = content
      lastSavedTime.value = new Date()

      if (emit) {
        emit('edit', updatedEntity)
      }
    } catch (error) {
      console.error('Failed to save entity notes:', error)
    } finally {
      saving.value = false
    }
  }

  let saveTimeout
  const triggerSave = () => {
    clearTimeout(saveTimeout)
    saveTimeout = setTimeout(saveNotes, 5000)
  }

  const editor = useEditor({
    content: entity.value?.data?.notes || '',
    editable: isEditing.value,
    extensions: [
      StarterKit.configure({
        taskList: false,
      }),
      Underline,
      Link,
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
          return isEditing.value
            ? 'Write your entity notes here... Use / for commands.'
            : 'Notes (read-only)'
        },
      }),
    ],
    shouldRerenderOnTransaction: false,
    onUpdate: ({ editor }) => {
      const content = editor.getHTML()
      if (isEditing.value) {
        // Update the form data so main form save includes latest notes
        if (formData && formData.value) {
          formData.value.data.notes = content
        }
        triggerSave()
      }
    },
    editorProps: {
      attributes: {
        class: `tiptap-editor focus:outline-none`,
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
      editor.value.commands.setContent(newVal || '', false)
      lastSaved.value = newVal || ''
    }
  }

  // Watch for entity changes and update editor content
  watch(
    () => entity.value?.data?.notes,
    (newNotes) => {
      if (newNotes !== undefined && editor.value) {
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
          const content = editor.value.getHTML()
          if (content !== lastSaved.value) {
            saveNotes()
          }
        }
        editor.value.setEditable(newEditingState)
      }
    },
  )

  const cleanup = () => {
    clearTimeout(saveTimeout)
    if (editor.value) {
      const content = editor.value.getHTML()
      if (content !== lastSaved.value) {
        saveNotes()
      }
      editor.value.destroy()
    }
  }

  onBeforeUnmount(cleanup)

  return {
    editor,
    editorActions,
    saving,
    lastSavedTime,
    formatLastSaved,
    updateContent,
    cleanup,
    saveNotes,
  }
}
