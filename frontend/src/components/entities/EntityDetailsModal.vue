<template>
  <v-dialog
    v-model="dialogVisible"
    :aria-label="entityTitle"
    max-width="1200px"
    persistent
    scrollable
    @keydown.esc="handleEscape"
  >
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start :icon="entityType(acknowledgedEntity.entity_type)?.icon" color="primary" />
        <span id="entity-details-dialog-title" class="text-headline-small">
          {{ entityTitle }}
        </span>
        <v-spacer />
        <v-chip :color="isEditing ? 'warning' : 'primary'" size="small" variant="tonal">
          {{ isEditing ? 'Editing' : 'View Mode' }}
        </v-chip>
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-0">
        <!-- Error Alert -->
        <EntityDuplicateAdvisory
          :candidates="advisories.candidates.value"
          :case-id="caseId"
          :entity-type="entity.entity_type"
          :loading="updating"
          @continue="handleSubmit(true)"
        />
        <v-alert v-if="error" type="error" variant="tonal" class="ma-4">
          {{ error }}
        </v-alert>

        <!-- Tabs -->
        <v-tabs v-model="activeTab" align-tabs="start" class="border-b" color="primary">
          <v-tab
            v-for="(section, key) in entitySchema"
            :key="key"
            :value="key"
            :prepend-icon="sectionIcon(key)"
          >
            {{ section.title }}
          </v-tab>
        </v-tabs>

        <v-tabs-window v-model="activeTab" class="pa-4">
          <v-tabs-window-item v-for="(section, key) in entitySchema" :key="key" :value="key">
            <!-- Notes Tab -->
            <div v-if="section.isNoteEditor && !notesExpanded" ref="notesTab">
              <EditorToolbar
                v-if="noteEditor"
                :actions="noteEditorActions"
                :disabled="!isEditing"
                :saving="noteSaving"
                :last-saved-time="noteLastSavedTime"
                :format-last-saved="noteFormatLastSaved"
                :expanded="notesExpanded"
                @toggle-expand="notesExpanded = !notesExpanded"
              />
              <v-alert v-if="noteSaveError" type="error">{{ noteSaveError }}</v-alert>
              <v-card
                :class="{ 'read-only-notes': !isEditing }"
                class="pa-4 mt-3"
                variant="outlined"
              >
                <editor-content v-if="noteEditor" :editor="noteEditor" class="tiptap-content" />
                <div v-else class="text-center pa-4 text-grey">
                  <v-icon>mdi-note-text</v-icon>
                  <p>Loading notes editor...</p>
                </div>
              </v-card>
            </div>

            <!-- Edit Mode Form -->
            <v-form v-else-if="isEditing" @submit.prevent="handleSubmit()">
              <v-container fluid class="pa-0">
                <v-row>
                  <EntityFormField
                    v-for="field in section.fields"
                    :key="field.id"
                    :field="field"
                    :field-value="getFieldValue(section.parentField, field.id)"
                    :source-value="getSourceValue(section.parentField, field.id)"
                    :entity="acknowledgedEntity"
                    @update:field="updateFieldValue(section.parentField, field.id, $event)"
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
                  :entity="acknowledgedEntity"
                  :source-value="getSourceValue(section.parentField, field.id)"
                />
              </v-row>
            </v-container>
          </v-tabs-window-item>
        </v-tabs-window>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-4">
        <v-spacer />
        <template v-if="isEditing">
          <v-btn :disabled="updating" prepend-icon="mdi-close" variant="text" @click="cancelEdit">
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-content-save"
            @click="handleSubmit()"
            :disabled="updating"
            :loading="updating"
          >
            {{ updating ? 'Saving...' : 'Save Changes' }}
          </v-btn>
        </template>
        <template v-else>
          <v-btn prepend-icon="mdi-close" variant="text" @click="handleClose"> Close </v-btn>
          <v-btn
            color="primary"
            prepend-icon="mdi-pencil"
            variant="flat"
            :disabled="closing"
            @click="startEditing"
          >
            Edit Entity
          </v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Fullscreen Notes Editor -->
  <EntityNotesFullscreen
    v-model:show="notesExpanded"
    :title="entityTitle"
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
import EntityDuplicateAdvisory from './EntityDuplicateAdvisory.vue'
import { ref, computed, toRef, watch } from 'vue'
import { EditorContent } from '@tiptap/vue-3'
import EntityFormField from './EntityFormField.vue'
import EntityViewField from './EntityViewField.vue'
import EditorToolbar from '../editor/EditorToolbar.vue'
import EntityNotesFullscreen from './EntityNotesFullscreen.vue'
import { useEntityDetails } from '../../composables/useEntityDetails.js'
import { entityType, sectionIcon } from '../../composables/entityTypes.js'
import { getEntityDisplayName } from '../../composables/entityDisplay.js'
import { useDialogFocusRestore } from '../../composables/useDialogFocusRestore.js'

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  entity: { type: Object, required: true },
  caseId: { type: Number, required: true },
  restoreFocusTo: { type: Function, default: null },
})

useDialogFocusRestore(
  () => props.show,
  () => props.restoreFocusTo?.(),
)

const emit = defineEmits(['close', 'edit'])

const notesExpanded = ref(false)
const closing = ref(false)
const notesTab = ref(null)
useDialogFocusRestore(
  () => notesExpanded.value,
  () => notesTab.value?.[0]?.querySelector('[aria-label="Expand to fullscreen"]'),
)

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      handleClose()
    }
  },
})

const entity = toRef(props, 'entity')
const caseId = toRef(props, 'caseId')

const {
  advisories,
  error,
  isEditing,
  updating,
  activeTab,
  acknowledgedEntity,
  getFieldValue,
  updateFieldValue,
  getSourceValue,
  updateSourceValue,
  entitySchema,
  startEditing,
  cancelEdit,
  updateEntity,
  editor: noteEditor,
  editorActions: noteEditorActions,
  saving: noteSaving,
  saveError: noteSaveError,
  lastSavedTime: noteLastSavedTime,
  formatLastSaved: noteFormatLastSaved,
  saveNotes,
} = useEntityDetails(entity, caseId, emit)

const entityTitle = computed(() => getEntityDisplayName(acknowledgedEntity.value))

watch(
  () => props.show,
  (show) => {
    if (!show) saveNotes()
  },
)

function handleEscape() {
  if (updating.value) return
  if (isEditing.value) {
    cancelEdit()
  } else {
    handleClose()
  }
}

async function handleClose() {
  if (closing.value || updating.value) return
  closing.value = true
  try {
    if (await saveNotes()) emit('close')
  } finally {
    closing.value = false
  }
}

async function handleSubmit(confirmed = false) {
  try {
    await updateEntity(confirmed === true)
  } catch {
    // Error handled in composable
  }
}
</script>
