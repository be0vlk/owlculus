<template>
  <v-dialog v-model="dialogVisible" max-width="900px" persistent scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start :icon="getEntityIcon" color="primary" />
        <span class="text-h5">{{ getEntityTitle }}</span>
        <v-spacer />
        <v-chip 
          :color="isEditing ? 'warning' : 'primary'" 
          variant="tonal" 
          size="small"
        >
          {{ isEditing ? 'Editing' : 'View Mode' }}
        </v-chip>
      </v-card-title>
      
      <v-divider />
      
      <v-card-text class="pa-0">
        <!-- Error Alert -->
        <v-alert v-if="error" type="error" variant="tonal" class="ma-4">
          {{ error }}
        </v-alert>

        <!-- Tabs -->
        <v-tabs 
          v-model="activeTab" 
          color="primary" 
          align-tabs="start"
          class="border-b"
        >
          <v-tab
            v-for="(section, key) in entitySchema"
            :key="key"
            :value="key"
            :prepend-icon="getSectionIcon(key)"
          >
            {{ section.title }}
          </v-tab>
        </v-tabs>

        <!-- Tab Contents -->
        <v-tabs-window v-model="activeTab" class="pa-4">
              <v-tabs-window-item
                v-for="(section, key) in entitySchema"
                :key="key"
                :value="key"
              >
                <!-- Notes Tab -->
                <div v-if="section.isNoteEditor && !notesExpanded" class="note-editor-container">
                  <EditorToolbar
                    v-if="isEditing"
                    :actions="noteEditorActions"
                    :saving="noteSaving"
                    :last-saved-time="noteLastSavedTime"
                    :format-last-saved="noteFormatLastSaved"
                    :expanded="notesExpanded"
                    @toggle-expand="notesExpanded = !notesExpanded"
                  />
                  <v-card 
                    variant="outlined" 
                    class="pa-4" 
                    :class="{ 'mt-3': isEditing, 'read-only-notes': !isEditing }"
                  >
                    <editor-content :editor="noteEditor" class="tiptap-content" />
                  </v-card>
                </div>

                <!-- Edit Mode Form -->
                <v-form v-else-if="isEditing" @submit.prevent="handleSubmit" ref="formRef">
                  <v-container fluid class="pa-0">
                    <v-row>
                      <template v-for="field in section.fields" :key="field.id">
                        <v-col :cols="field.gridCols === 2 ? 12 : 6">
                          <v-textarea
                            v-if="field.type === 'textarea'"
                            v-model="formData.data[section.parentField ? `${section.parentField}.${field.id}` : field.id]"
                            :label="field.label"
                            variant="outlined"
                            density="comfortable"
                            rows="3"
                            auto-grow
                            clearable
                          />
                          <v-text-field
                            v-else
                            v-model="formData.data[section.parentField ? `${section.parentField}.${field.id}` : field.id]"
                            :label="field.label"
                            :type="field.type"
                            variant="outlined"
                            density="comfortable"
                            clearable
                            :prepend-inner-icon="getFieldIcon(field.type)"
                          />
                        </v-col>
                      </template>
                    </v-row>
                  </v-container>
                </v-form>

                <!-- View Mode -->
                <v-container v-else fluid class="pa-0">
                  <v-row>
                    <template v-for="field in section.fields" :key="field.id">
                      <v-col :cols="field.gridCols === 2 ? 12 : 6">
                        <v-card variant="outlined" class="pa-3">
                          <v-card-subtitle class="pa-0 pb-2">
                            <v-icon 
                              :icon="getFieldIcon(field.type)" 
                              size="small" 
                              class="me-2"
                            />
                            {{ field.label }}
                          </v-card-subtitle>
                          
                          <!-- Associates Section -->
                          <div v-if="section.parentField === 'associates'">
                            <div v-if="getAssociateEntities(field.id).length > 0" class="mb-2">
                              <EntityTag
                                v-for="associate in getAssociateEntities(field.id)"
                                :key="associate.id"
                                @click="$emit('viewEntity', associate)"
                                class="ma-1"
                              >
                                {{ getEntityDisplayName(associate) }}
                              </EntityTag>
                            </div>
                            <v-chip v-else variant="text" color="grey" size="small">
                              {{ getFieldValue(entity.data, section.parentField, field.id) || 'Not specified' }}
                            </v-chip>
                          </div>
                          
                          <!-- URL Fields -->
                          <div v-else-if="field.type === 'url'">
                            <v-btn
                              v-if="getFieldValue(entity.data, section.parentField, field.id)"
                              :href="getFieldValue(entity.data, section.parentField, field.id)"
                              target="_blank"
                              variant="outlined"
                              color="primary"
                              size="small"
                              prepend-icon="mdi-open-in-new"
                              class="ma-0"
                            >
                              {{ getFieldValue(entity.data, section.parentField, field.id) }}
                            </v-btn>
                            <v-chip v-else variant="text" color="grey" size="small">
                              Not provided
                            </v-chip>
                          </div>
                          
                          <!-- Regular Fields -->
                          <div v-else class="text-body-1">
                            <span v-if="getFieldValue(entity.data, section.parentField, field.id)">
                              {{ getFieldValue(entity.data, section.parentField, field.id) }}
                            </span>
                            <v-chip v-else variant="text" color="grey" size="small">
                              Not provided
                            </v-chip>
                          </div>
                        </v-card>
                      </v-col>
                    </template>
                  </v-row>
                </v-container>
              </v-tabs-window-item>
            </v-tabs-window>

      </v-card-text>
      
      <v-divider />
      
      <v-card-actions class="pa-4">
        <v-spacer />
        
        <!-- Edit Mode Actions -->
        <template v-if="isEditing">
          <v-btn
            variant="text"
            prepend-icon="mdi-close"
            @click="cancelEdit"
            :disabled="updating"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-content-save"
            @click="handleSubmit"
            :disabled="updating"
            :loading="updating"
          >
            {{ updating ? 'Saving...' : 'Save Changes' }}
          </v-btn>
        </template>
        
        <!-- View Mode Actions -->
        <template v-else>
          <v-btn
            variant="text"
            prepend-icon="mdi-close"
            @click="$emit('close')"
          >
            Close
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-pencil"
            @click="startEditing"
          >
            Edit Entity
          </v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Fullscreen Notes Editor -->
  <v-dialog
    v-model="notesExpanded"
    fullscreen
    transition="dialog-bottom-transition"
    :scrim="true"
  >
    <v-card class="d-flex flex-column" style="height: 100vh;">
      <v-toolbar color="primary" dark>
        <v-toolbar-title>
          <v-icon start>mdi-note-text</v-icon>
          {{ getEntityTitle }} - Notes
        </v-toolbar-title>
        <v-spacer />
        <v-btn
          icon="mdi-close"
          @click="notesExpanded = false"
        />
      </v-toolbar>

      <div class="flex-grow-1 d-flex flex-column overflow-hidden">
        <EditorToolbar
          v-if="isEditing"
          :actions="noteEditorActions"
          :saving="noteSaving"
          :last-saved-time="noteLastSavedTime"
          :format-last-saved="noteFormatLastSaved"
          :expanded="notesExpanded"
          @toggle-expand="notesExpanded = !notesExpanded"
        />

        <v-container fluid class="flex-grow-1 overflow-auto pa-6">
          <v-row justify="center">
            <v-col cols="12" lg="10" xl="8">
              <editor-content :editor="noteEditor" class="tiptap-content fullscreen-editor" />
            </v-col>
          </v-row>
        </v-container>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, toRef } from 'vue'
import { EditorContent } from '@tiptap/vue-3'
import EntityTag from './EntityTag.vue'
import EditorToolbar from './editor/EditorToolbar.vue'
import { useEntityDetails } from '../composables/useEntityDetails'
import { useEntityAssociates } from '../composables/useEntityAssociates'
import { useEntityIcons } from '../composables/useEntityIcons'
import { useEntityDisplay } from '../composables/useEntityDisplay'
import { useEntityNoteEditor } from '../composables/useEntityNoteEditor'

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  entity: { type: Object, required: true },
  caseId: { type: Number, required: true },
  existingEntities: { type: Array, required: true },
})

const emit = defineEmits(['close', 'edit', 'viewEntity'])

const notesExpanded = ref(false)

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
})

const entity = toRef(props, 'entity')
const caseId = toRef(props, 'caseId')
const existingEntities = toRef(props, 'existingEntities')

const {
  error,
  isEditing,
  updating,
  activeTab,
  formData,
  entitySchema,
  startEditing,
  cancelEdit,
  updateEntity
} = useEntityDetails(entity, caseId)

const {
  getAssociateEntities,
  processAssociates
} = useEntityAssociates(entity, existingEntities, caseId)

const {
  getEntityIcon,
  getSectionIcon,
  getFieldIcon
} = useEntityIcons(entity)

const {
  getEntityDisplayName,
  getEntityTitle,
  getFieldValue
} = useEntityDisplay(entity)

const {
  editor: noteEditor,
  editorActions: noteEditorActions,
  saving: noteSaving,
  lastSavedTime: noteLastSavedTime,
  formatLastSaved: noteFormatLastSaved
} = useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

async function handleSubmit() {
  try {
    const { updatedEntity, createdAssociates } = await updateEntity(processAssociates)
    
    if (createdAssociates.length > 0) {
      emit('edit', updatedEntity, createdAssociates)
    } else {
      emit('edit', updatedEntity)
    }
  } catch (err) {
    // Error handled in composable
  }
}

</script>

<style scoped>
.note-editor-container .tiptap-content .ProseMirror {
  outline: none;
  min-height: 200px;
}

.note-editor-container .tiptap-content .ProseMirror p.is-editor-empty:first-child::before {
  color: rgb(var(--v-theme-on-surface-variant));
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}

.note-editor-container .tiptap-content h1,
.note-editor-container .tiptap-content h2,
.note-editor-container .tiptap-content h3 {
  margin: 16px 0 8px;
  line-height: 1.2;
  font-weight: 600;
}

.note-editor-container .tiptap-content h1 { font-size: 1.5rem; }
.note-editor-container .tiptap-content h2 { font-size: 1.3rem; }
.note-editor-container .tiptap-content h3 { font-size: 1.1rem; }

.note-editor-container .tiptap-content ul,
.note-editor-container .tiptap-content ol {
  padding-left: 24px;
  margin: 8px 0;
}

.note-editor-container .tiptap-content blockquote {
  border-left: 4px solid rgb(var(--v-theme-primary));
  margin: 16px 0;
  padding-left: 16px;
  font-style: italic;
  color: rgb(var(--v-theme-on-surface-variant));
}

.note-editor-container .tiptap-content a {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}

.note-editor-container .tiptap-content p {
  margin: 8px 0;
}

.note-editor-container .tiptap-content mark {
  background-color: rgb(var(--v-theme-warning));
  padding: 0 2px;
  border-radius: 2px;
}

.note-editor-container .tiptap-content .task-list {
  list-style: none;
  padding-left: 0;
}

.note-editor-container .tiptap-content .task-item {
  display: flex;
  align-items: flex-start;
  margin: 4px 0;
}

.note-editor-container .tiptap-content .task-item > label {
  flex: 0 0 auto;
  margin-right: 8px;
  margin-top: 2px;
  user-select: none;
}

.note-editor-container .tiptap-content .task-item > div {
  flex: 1 1 auto;
}

.note-editor-container .tiptap-content .task-item input[type="checkbox"] {
  margin: 0;
}

.note-editor-container .tiptap-content .task-item[data-checked="true"] > div {
  text-decoration: line-through;
  opacity: 0.6;
}

/* Read-only styling */
.read-only-notes {
  opacity: 0.7;
}

.read-only-notes .tiptap-content .ProseMirror {
  cursor: default;
}

.read-only-notes .tiptap-content .ProseMirror * {
  pointer-events: none;
}

/* Full screen editor styles */
.fullscreen-editor .ProseMirror {
  outline: none;
  min-height: 400px;
  background: rgb(var(--v-theme-surface));
  border-radius: 4px;
  padding: 24px;
}

.fullscreen-editor .ProseMirror:focus {
  box-shadow: 0 0 0 2px rgba(var(--v-theme-primary), 0.2);
}

.fullscreen-editor .ProseMirror p.is-editor-empty:first-child::before {
  color: rgb(var(--v-theme-on-surface-variant));
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}
</style>