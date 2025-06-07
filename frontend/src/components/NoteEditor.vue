<template>
  <v-card variant="outlined" class="note-editor">
    <!-- Toolbar -->
    <v-toolbar density="compact" color="surface" class="border-b">
      <v-btn-group variant="text" density="compact">
        <v-btn
          v-for="(action, index) in editorActions"
          :key="index"
          :icon="action.icon"
          size="small"
          :variant="action.isActive?.() ? 'tonal' : 'text'"
          :color="action.isActive?.() ? 'primary' : 'default'"
          @click="action.action"
          :title="action.title"
        />
      </v-btn-group>
      
      <v-spacer />
      
      <div class="text-caption text-medium-emphasis">
        <v-progress-circular
          v-if="saving"
          size="16"
          width="2"
          indeterminate
          class="mr-2"
        />
        <span v-if="saving">Saving...</span>
        <span v-else-if="lastSavedTime">Last saved: {{ formatLastSaved }}</span>
      </div>
    </v-toolbar>

    <!-- Editor Content -->
    <v-card-text class="pa-4" style="min-height: 200px;">
      <editor-content :editor="editor" class="tiptap-content" />
    </v-card-text>
  </v-card>
</template>

<script setup>
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import Highlight from '@tiptap/extension-highlight';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableHeader from '@tiptap/extension-table-header';
import TableCell from '@tiptap/extension-table-cell';
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

const editor = useEditor({
  content: props.modelValue || '',
  extensions: [
    StarterKit.configure({
      // Disable default TaskList from StarterKit to use our custom one
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
    Table.configure({
      resizable: true,
      HTMLAttributes: {
        class: 'tiptap-table',
      },
    }),
    TableRow,
    TableHeader,
    TableCell,
    Placeholder.configure({
      placeholder: ({ node }) => {
        if (node.type.name === 'heading') {
          return "What's the title?";
        }
        return 'Write your case notes here... Use / for commands.';
      },
    }),
  ],
  // Performance optimization - prevent unnecessary re-renders
  shouldRerenderOnTransaction: false,
  onUpdate: ({ editor }) => {
    const content = editor.getHTML();
    emit('update:modelValue', content);
    triggerSave();
  },
  editorProps: {
    attributes: {
      class: 'tiptap-editor focus:outline-none',
      style: 'min-height: 150px;',
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
  {
    icon: 'mdi-table',
    title: 'Insert Table',
    action: () => editor.value?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(),
    isActive: () => editor.value?.isActive('table'),
  },
]);

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

<style scoped>
.note-editor .tiptap-content .ProseMirror {
  outline: none;
  min-height: 150px;
}

.note-editor .tiptap-content .ProseMirror p.is-editor-empty:first-child::before {
  color: rgb(var(--v-theme-on-surface-variant));
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}

/* TipTap editor content styling */
.note-editor .tiptap-content h1,
.note-editor .tiptap-content h2,
.note-editor .tiptap-content h3 {
  margin: 16px 0 8px;
  line-height: 1.2;
  font-weight: 600;
}

.note-editor .tiptap-content h1 { font-size: 1.5rem; }
.note-editor .tiptap-content h2 { font-size: 1.3rem; }
.note-editor .tiptap-content h3 { font-size: 1.1rem; }

.note-editor .tiptap-content ul,
.note-editor .tiptap-content ol {
  padding-left: 24px;
  margin: 8px 0;
}

.note-editor .tiptap-content blockquote {
  border-left: 4px solid rgb(var(--v-theme-primary));
  margin: 16px 0;
  padding-left: 16px;
  font-style: italic;
  color: rgb(var(--v-theme-on-surface-variant));
}

.note-editor .tiptap-content a {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}

.note-editor .tiptap-content p {
  margin: 8px 0;
}

/* Highlight styling */
.note-editor .tiptap-content mark {
  background-color: rgb(var(--v-theme-warning));
  padding: 0 2px;
  border-radius: 2px;
}

/* Task list styling */
.note-editor .tiptap-content .task-list {
  list-style: none;
  padding-left: 0;
}

.note-editor .tiptap-content .task-item {
  display: flex;
  align-items: flex-start;
  margin: 4px 0;
}

.note-editor .tiptap-content .task-item > label {
  flex: 0 0 auto;
  margin-right: 8px;
  margin-top: 2px;
  user-select: none;
}

.note-editor .tiptap-content .task-item > div {
  flex: 1 1 auto;
}

.note-editor .tiptap-content .task-item input[type="checkbox"] {
  margin: 0;
}

.note-editor .tiptap-content .task-item[data-checked="true"] > div {
  text-decoration: line-through;
  opacity: 0.6;
}

/* Table styling */
.note-editor .tiptap-content .tiptap-table {
  border-collapse: collapse;
  margin: 16px 0;
  table-layout: fixed;
  width: 100%;
}

.note-editor .tiptap-content .tiptap-table td,
.note-editor .tiptap-content .tiptap-table th {
  border: 1px solid rgb(var(--v-theme-outline-variant));
  box-sizing: border-box;
  min-width: 1em;
  padding: 8px 12px;
  position: relative;
  vertical-align: top;
}

.note-editor .tiptap-content .tiptap-table th {
  background-color: rgb(var(--v-theme-surface-variant));
  font-weight: 600;
  text-align: left;
}

.note-editor .tiptap-content .tiptap-table .selectedCell::after {
  background-color: rgb(var(--v-theme-primary), 0.1);
  content: "";
  inset: 0;
  pointer-events: none;
  position: absolute;
  z-index: 2;
}
</style>