<template>
  <div class="note-editor">
    <div class="editor-toolbar border-b border-gray-200 dark:border-gray-700 p-2 flex gap-2">
      <button
        v-for="(action, index) in editorActions"
        :key="index"
        @click="action.action"
        :class="[
          'p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300',
          { 'bg-gray-100 dark:bg-gray-700': action.isActive?.() }
        ]"
        :title="action.title"
      >
        <font-awesome-icon :icon="action.icon" />
      </button>
    </div>
    <div class="p-4 min-h-[200px] bg-white dark:bg-gray-800">
      <editor-content :editor="editor" class="prose dark:prose-invert max-w-none text-gray-900 dark:text-gray-100" />
    </div>
    <div class="flex justify-end p-2 text-sm text-gray-500 dark:text-gray-400">
      <span v-if="saving">Saving...</span>
      <span v-else-if="lastSavedTime">Last saved: {{ formatLastSaved }}</span>
    </div>
  </div>
</template>

<script setup>
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import { onBeforeUnmount, ref, watch, defineEmits, defineProps, computed } from 'vue';
import { caseService } from '../services/case';
import Placeholder from '@tiptap/extension-placeholder';
import { formatDistanceToNow } from 'date-fns';

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  caseId: {
    type: Number,
    required: true,
  },
});

const emit = defineEmits(['update:modelValue']);

const lastSaved = ref(null);
const lastSavedTime = ref(null);
const saving = ref(false);

const formatLastSaved = computed(() => {
  if (!lastSavedTime.value) return '';
  return formatDistanceToNow(lastSavedTime.value, { addSuffix: true });
});

const editorActions = computed(() => [
  {
    icon: ['fas', 'bold'],
    title: 'Bold',
    action: () => editor.value?.chain().focus().toggleBold().run(),
    isActive: () => editor.value?.isActive('bold'),
  },
  {
    icon: ['fas', 'italic'],
    title: 'Italic',
    action: () => editor.value?.chain().focus().toggleItalic().run(),
    isActive: () => editor.value?.isActive('italic'),
  },
  {
    icon: ['fas', 'underline'],
    title: 'Underline',
    action: () => editor.value?.chain().focus().toggleUnderline().run(),
    isActive: () => editor.value?.isActive('underline'),
  },
  {
    icon: ['fas', 'strikethrough'],
    title: 'Strike',
    action: () => editor.value?.chain().focus().toggleStrike().run(),
    isActive: () => editor.value?.isActive('strike'),
  },
  {
    icon: ['fas', 'list-ul'],
    title: 'Bullet List',
    action: () => editor.value?.chain().focus().toggleBulletList().run(),
    isActive: () => editor.value?.isActive('bulletList'),
  },
  {
    icon: ['fas', 'list-ol'],
    title: 'Ordered List',
    action: () => editor.value?.chain().focus().toggleOrderedList().run(),
    isActive: () => editor.value?.isActive('orderedList'),
  },
  {
    icon: ['fas', 'quote-right'],
    title: 'Blockquote',
    action: () => editor.value?.chain().focus().toggleBlockquote().run(),
    isActive: () => editor.value?.isActive('blockquote'),
  },
]);

const editor = useEditor({
  content: props.modelValue || '',
  extensions: [
    StarterKit,
    Underline,
    Link,
    Placeholder.configure({
      placeholder: 'Write your notes here...',
    }),
  ],
  onUpdate: ({ editor }) => {
    const content = editor.getHTML();
    emit('update:modelValue', content);
    triggerSave();
  },
  editorProps: {
    attributes: {
      class: 'prose dark:prose-invert focus:outline-none min-h-[150px] text-gray-900 dark:text-gray-100',
    },
  },
});

watch(
  () => props.modelValue,
  (newVal) => {
    const currentContent = editor.value?.getHTML();
    if (newVal !== currentContent && editor.value) {
      editor.value.commands.setContent(newVal || '', false);
    }
  }
);

const saveNotes = async () => {
  if (!editor.value) return;
  
  const content = editor.value.getHTML();
  if (content === lastSaved.value) return;
  
  try {
    saving.value = true;
    await caseService.updateCase(props.caseId, { notes: content });
    lastSaved.value = content;
    lastSavedTime.value = new Date();
  } catch (error) {
    console.error('Failed to save notes:', error);
  } finally {
    saving.value = false;
  }
};

let saveTimeout;
const triggerSave = () => {
  clearTimeout(saveTimeout);
  saveTimeout = setTimeout(saveNotes, 1000);
};

onBeforeUnmount(() => {
  clearTimeout(saveTimeout);
  if (editor.value) {
    const content = editor.value.getHTML();
    if (content !== lastSaved.value) {
      saveNotes();
    }
    editor.value.destroy();
  }
});
</script>

<style>
.note-editor {
  @apply border rounded-lg dark:border-gray-700;
}

.note-editor .ProseMirror {
  @apply min-h-[200px] outline-none;
}

.note-editor .ProseMirror p.is-editor-empty:first-child::before {
  @apply text-gray-400 dark:text-gray-500;
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}

/* Additional styling for the editor content */
.note-editor .prose {
  @apply max-w-none;
}

.note-editor .prose :where(blockquote):not(:where([class~="not-prose"] *)) {
  @apply border-l-4 border-gray-300 dark:border-gray-600;
}

.note-editor .prose :where(ul > li):not(:where([class~="not-prose"] *))::marker {
  @apply text-gray-500 dark:text-gray-400;
}

.note-editor .prose :where(ol > li):not(:where([class~="not-prose"] *))::marker {
  @apply text-gray-500 dark:text-gray-400;
}
</style>