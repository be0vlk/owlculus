<template>
  <v-tabs-window :model-value="activeTab" class="pa-4">
    <v-tabs-window-item v-for="(section, key) in entitySchema" :key="key" :value="key">
      <!-- Notes Tab -->
      <div v-if="section.isNoteEditor && !notesExpanded" class="note-editor-container">
        <EditorToolbar
          v-if="noteEditor"
          :actions="noteEditorActions"
          :saving="noteSaving"
          :last-saved-time="noteLastSavedTime"
          :format-last-saved="noteFormatLastSaved"
          :expanded="notesExpanded"
          @toggle-expand="$emit('toggleExpand')"
        />
        <v-card :class="{ 'read-only-notes': !isEditing }" class="pa-4 mt-3" variant="outlined">
          <editor-content v-if="noteEditor" :editor="noteEditor" class="tiptap-content" />
          <div v-else class="text-center pa-4 text-grey">
            <v-icon>mdi-note-text</v-icon>
            <p>Loading notes editor...</p>
          </div>
        </v-card>
      </div>

      <!-- Edit Mode Form -->
      <v-form v-else-if="isEditing" @submit.prevent="$emit('submit')" ref="formRef">
        <v-container fluid class="pa-0">
          <v-row>
            <EntityFormField
              v-for="field in section.fields"
              :key="field.id"
              :field="field"
              :field-value="getFieldValue(section, field)"
              :source-value="getSourceValue(section.parentField, field.id)"
              :entity="entity"
              @update:field="updateFieldValue(section, field, $event)"
              @update:source="updateSourceValue(section.parentField, field.id, $event)"
            />
          </v-row>
        </v-container>
      </v-form>

      <!-- View Mode -->
      <v-container v-else fluid class="pa-0">
        <v-row>
          <EntityViewField
            v-for="field in section.fields"
            :key="field.id"
            :field="field"
            :section="section"
            :entity="entity"
            :source-value="getSourceValue(section.parentField, field.id)"
            :get-associate-entities="getAssociateEntities"
            :existing-entities="existingEntities"
            @view-entity="$emit('viewEntity', $event)"
          />
        </v-row>
      </v-container>
    </v-tabs-window-item>
  </v-tabs-window>
</template>

<script setup>
import { EditorContent } from '@tiptap/vue-3'
import EntityFormField from './EntityFormField.vue'
import EntityViewField from './EntityViewField.vue'
import EditorToolbar from '../editor/EditorToolbar.vue'

const props = defineProps({
  activeTab: { type: String, required: true },
  entitySchema: { type: Object, required: true },
  isEditing: { type: Boolean, required: true },
  entity: { type: Object, required: true },
  formData: { type: Object, required: true },
  notesExpanded: { type: Boolean, required: true },
  noteEditor: { type: Object, default: null },
  noteEditorActions: { type: Array, default: () => [] },
  noteSaving: { type: Boolean, default: false },
  noteLastSavedTime: { type: [Date, null], default: null },
  noteFormatLastSaved: { type: String, default: '' },
  getSourceValue: { type: Function, required: true },
  updateSourceValue: { type: Function, required: true },
  getAssociateEntities: { type: Function, required: true },
  existingEntities: { type: Array, required: true },
})

const emit = defineEmits(['submit', 'toggleExpand', 'viewEntity', 'updateField'])

function getFieldValue(section, field) {
  const fieldPath = section.parentField ? `${section.parentField}.${field.id}` : field.id
  return props.formData.data[fieldPath] || ''
}

function updateFieldValue(section, field, value) {
  const fieldPath = section.parentField ? `${section.parentField}.${field.id}` : field.id
  emit('updateField', fieldPath, value)
}
</script>

<style scoped>
@import '../../styles/entity-editor.css';
</style>
