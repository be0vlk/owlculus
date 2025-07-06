<template>
  <v-dialog v-model="dialogVisible" max-width="1200px" persistent scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start :icon="getEntityIcon" color="primary" />
        <span class="text-h5">{{ getEntityTitle }}</span>
        <v-spacer />
        <v-chip :color="isEditing ? 'warning' : 'primary'" size="small" variant="tonal">
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
        <v-tabs v-model="activeTab" align-tabs="start" class="border-b" color="primary">
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
        <EntityTabContent
          :active-tab="activeTab"
          :entity-schema="entitySchema"
          :is-editing="isEditing"
          :entity="entity"
          :form-data="formData"
          :notes-expanded="notesExpanded"
          :note-editor="noteEditor"
          :note-editor-actions="noteEditorActions"
          :note-saving="noteSaving"
          :note-last-saved-time="noteLastSavedTime"
          :note-format-last-saved="noteFormatLastSaved"
          :get-source-value="getSourceValue"
          :update-source-value="updateSourceValue"
          :get-associate-entities="getAssociateEntities"
          :existing-entities="existingEntities"
          @submit="handleSubmit"
          @toggle-expand="notesExpanded = !notesExpanded"
          @view-entity="$emit('viewEntity', $event)"
          @update-field="handleFieldUpdate"
        />
      </v-card-text>

      <v-divider />

      <EntityModalActions
        :is-editing="isEditing"
        :updating="updating"
        @close="$emit('close')"
        @edit="startEditing"
        @cancel="cancelEdit"
        @save="handleSubmit"
      />
    </v-card>
  </v-dialog>

  <!-- Fullscreen Notes Editor -->
  <EntityNotesFullscreen
    v-model:show="notesExpanded"
    :title="getEntityTitle"
    :editor="noteEditor"
    :editor-actions="noteEditorActions"
    :saving="noteSaving"
    :last-saved-time="noteLastSavedTime"
    :format-last-saved="noteFormatLastSaved"
    :is-editing="isEditing"
    @close="notesExpanded = false"
  />
</template>

<script setup>
import { ref, computed, toRef } from 'vue'
import EntityTabContent from './EntityTabContent.vue'
import EntityModalActions from './EntityModalActions.vue'
import EntityNotesFullscreen from './EntityNotesFullscreen.vue'
import { useEntityDetails } from '../../composables/useEntityDetails.js'
import { useEntityAssociates } from '../../composables/useEntityAssociates.js'
import { useEntityIcons } from '../../composables/useEntityIcons.js'
import { useEntityDisplay } from '../../composables/useEntityDisplay.js'
import { useEntityNoteEditor } from '../../composables/useEntityNoteEditor.js'
import { useEntitySources } from '../../composables/useEntitySources.js'

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
  },
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
  updateEntity,
} = useEntityDetails(entity, caseId)

const { getAssociateEntities, processAssociates } = useEntityAssociates(entity)

const { getEntityIcon, getSectionIcon } = useEntityIcons(entity)

const { getEntityTitle } = useEntityDisplay(entity)

const {
  editor: noteEditor,
  editorActions: noteEditorActions,
  saving: noteSaving,
  lastSavedTime: noteLastSavedTime,
  formatLastSaved: noteFormatLastSaved,
} = useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

const { getSourceValue, updateSourceValue } = useEntitySources(entity, formData, isEditing)

function handleFieldUpdate(fieldPath, value) {
  formData.value.data[fieldPath] = value
}

async function handleSubmit() {
  try {
    const { updatedEntity, createdAssociates } = await updateEntity(processAssociates)

    if (createdAssociates.length > 0) {
      emit('edit', updatedEntity, createdAssociates)
    } else {
      emit('edit', updatedEntity)
    }
  } catch {
    // Error handled in composable
  }
}
</script>
