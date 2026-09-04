<template>
  <v-dialog
    v-model="dialogVisible"
    :aria-label="getEntityTitle"
    max-width="1200px"
    persistent
    scrollable
    @keydown.esc="handleEscape"
  >
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start :icon="getEntityIcon" color="primary" />
        <span id="entity-details-dialog-title" class="text-headline-small">
          {{ getEntityTitle }}
        </span>
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
          :note-save-error="noteSaveError"
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
    :save-error="noteSaveError"
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
import { useDialogFocusRestore } from '../../composables/useDialogFocusRestore.js'

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  entity: { type: Object, required: true },
  caseId: { type: Number, required: true },
  existingEntities: { type: Array, required: true },
  restoreFocusTo: { type: Function, default: null },
})

useDialogFocusRestore(
  () => props.show,
  () => props.restoreFocusTo?.(),
)

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
  saveError: noteSaveError,
  lastSavedTime: noteLastSavedTime,
  formatLastSaved: noteFormatLastSaved,
} = useEntityNoteEditor(entity, caseId, isEditing, formData, emit)

const { getSourceValue, updateSourceValue } = useEntitySources(entity, formData, isEditing)

function handleFieldUpdate(fieldPath, value) {
  // Handle nested field paths (e.g., 'address.street' becomes data.address.street)
  if (fieldPath.includes('.')) {
    const parts = fieldPath.split('.')
    const parentField = parts[0]
    const childField = parts[1]

    // Ensure parent object exists
    if (!formData.value.data[parentField]) {
      formData.value.data[parentField] = {}
    }

    formData.value.data[parentField][childField] = value
  } else {
    formData.value.data[fieldPath] = value
  }
}

function handleEscape() {
  if (updating.value) return
  if (isEditing.value) {
    cancelEdit()
  } else {
    emit('close')
  }
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
