<template>
  <v-card :class="embedded ? 'admin-embedded' : 'mb-6'" :variant="embedded ? 'flat' : 'outlined'">
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <v-icon
        v-if="!embedded"
        icon="mdi-clipboard-text"
        color="primary"
        size="large"
        class="me-3"
      />
      <div class="flex-grow-1">
        <h2 class="text-title-large font-weight-bold">
          {{ embedded ? 'Task templates' : 'Task Templates' }}
        </h2>
        <div class="text-body-medium text-medium-emphasis">
          Manage reusable task templates for standardized workflows
        </div>
      </div>
      <v-btn
        color="primary"
        variant="flat"
        prepend-icon="mdi-plus"
        @click="openAddDialog"
        :disabled="loading"
      >
        Add Template
      </v-btn>
    </v-card-title>

    <v-divider />

    <v-card-text class="pa-0">
      <!-- Loading state -->
      <div v-if="loading" class="pa-6">
        <v-skeleton-loader type="table-row@5" />
      </div>

      <!-- Error state -->
      <v-alert v-else-if="error" :text="error" class="ma-4" type="error" variant="tonal" />

      <!-- Empty state -->
      <div v-else-if="!sortedTemplates.length" class="pa-8 text-center">
        <v-icon icon="mdi-clipboard-off" size="64" color="grey-darken-1" class="mb-4" />
        <div class="text-title-large text-medium-emphasis mb-2">No Task Templates</div>
        <div class="text-body-medium text-medium-emphasis mb-4">
          Create task templates to standardize your investigation workflows
        </div>
        <v-btn color="primary" prepend-icon="mdi-plus" variant="flat" @click="openAddDialog">
          Create Your First Template
        </v-btn>
      </div>

      <!-- Templates Table -->
      <v-table v-else class="admin-dashboard-table">
        <thead>
          <tr>
            <th class="operations-column">Template</th>
            <th class="operations-column">Category</th>
            <th class="operations-column">Custom Fields</th>
            <th class="operations-column">Status</th>
            <th class="operations-column">Created By</th>
            <th class="operations-column">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="template in sortedTemplates" :key="template.id">
            <td class="operations-cell">
              <div>
                <div class="font-weight-medium">{{ template.display_name }}</div>
                <div class="text-body-small text-medium-emphasis">{{ template.name }}</div>
              </div>
            </td>
            <td class="operations-cell">
              <v-chip size="small" variant="tonal">
                {{ template.category }}
              </v-chip>
            </td>
            <td class="operations-cell">
              <v-chip size="small" variant="tonal" color="info">
                {{ getFieldCount(template) }} fields
              </v-chip>
            </td>
            <td class="operations-cell">
              <v-chip size="small" :color="template.is_active ? 'success' : 'grey'" variant="tonal">
                {{ template.is_active ? 'Active' : 'Inactive' }}
              </v-chip>
            </td>
            <td class="operations-cell">
              <div v-if="template.creator" class="text-body-medium">
                {{ template.creator.username }}
              </div>
              <div v-else class="text-body-small text-medium-emphasis">System</div>
            </td>
            <td class="operations-cell">
              <div class="d-flex align-center" style="gap: 8px">
                <v-btn
                  color="primary"
                  size="small"
                  variant="outlined"
                  icon
                  @click="openEditDialog(template)"
                  :disabled="saving || deleting"
                  :aria-label="`Edit ${template.display_name}`"
                >
                  <v-icon>mdi-pencil</v-icon>
                  <v-tooltip activator="parent" location="top">
                    Edit {{ template.display_name }}
                  </v-tooltip>
                </v-btn>
                <v-btn
                  color="error"
                  size="small"
                  variant="outlined"
                  icon
                  @click="handleDeleteTemplate(template)"
                  :disabled="saving || deleting"
                  :aria-label="`Delete ${template.display_name}`"
                >
                  <v-icon>mdi-delete</v-icon>
                  <v-tooltip activator="parent" location="top">
                    Delete {{ template.display_name }}
                  </v-tooltip>
                </v-btn>
              </div>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card-text>

    <!-- Add Template Dialog -->
    <v-dialog aria-label="Add Task Template" v-model="showAddDialog" max-width="800" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon icon="mdi-plus" class="me-3" />
          Add Task Template
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <TaskTemplateForm
            :id="addFormId"
            ref="addFormRef"
            :disabled="saving"
            @submit="handleCreateTemplate"
            v-model="newTemplateForm"
            :validate-template-name="validateTemplateName"
            :validate-display-name="validateDisplayName"
            :validate-description="validateDescription"
            :validate-category="validateCategory"
          />
        </v-card-text>

        <v-divider />

        <v-card-actions class="pa-4 flex-wrap">
          <v-spacer />
          <v-btn :disabled="saving" variant="text" @click="closeAddDialog">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="saving" type="submit" :form="addFormId">
            Create Template
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Edit Template Dialog -->
    <v-dialog aria-label="Edit Task Template" v-model="showEditDialog" max-width="800" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon icon="mdi-pencil" class="me-3" />
          Edit Task Template - {{ editingTemplate?.display_name }}
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <TaskTemplateForm
            :id="editFormId"
            ref="editFormRef"
            :disabled="saving"
            @submit="handleUpdateTemplate"
            v-model="editTemplateForm"
            :is-edit="true"
            :validate-template-name="validateTemplateName"
            :validate-display-name="validateDisplayName"
            :validate-description="validateDescription"
            :validate-category="validateCategory"
          />
        </v-card-text>

        <v-divider />

        <v-card-actions class="pa-4 flex-wrap">
          <v-spacer />
          <v-btn :disabled="saving" variant="text" @click="closeEditDialog">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="saving" type="submit" :form="editFormId">
            Update Template
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
defineProps({ embedded: Boolean })
import { onMounted, ref, useId } from 'vue'
import { useTaskTemplates } from '@/composables/useTaskTemplates'
import TaskTemplateForm from './TaskTemplateForm.vue'

const emit = defineEmits(['notification', 'confirmDelete'])

// Form refs
const addFormId = useId()
const editFormId = useId()
const addFormRef = ref(null)
const editFormRef = ref(null)

// Use the task templates composable
const {
  // State
  loading,
  saving,
  deleting,
  error,
  showAddDialog,
  showEditDialog,
  editingTemplate,
  newTemplateForm,
  editTemplateForm,

  // Computed
  sortedTemplates,

  // Validation
  validateTemplateName,
  validateDisplayName,
  validateDescription,
  validateCategory,

  // Methods
  loadTemplates,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  openAddDialog,
  openEditDialog,
  closeAddDialog,
  closeEditDialog,
} = useTaskTemplates()

// Helper methods
const getFieldCount = (template) => {
  return template.definition_json?.fields?.length || 0
}

// Event handlers
const handleCreateTemplate = async () => {
  if (saving.value) return
  try {
    // Validate form
    const isValid = await addFormRef.value?.validate()
    if (!isValid) return

    await createTemplate()
    emit('notification', { text: 'Task template created successfully!', color: 'success' })
  } catch (error) {
    console.error('Error creating template:', error)
    emit('notification', { text: error.message || 'Failed to create template', color: 'error' })
  }
}

const handleUpdateTemplate = async () => {
  if (saving.value) return
  try {
    // Validate form
    const isValid = await editFormRef.value?.validate()
    if (!isValid) return

    await updateTemplate()
    emit('notification', { text: 'Task template updated successfully!', color: 'success' })
  } catch (error) {
    console.error('Error updating template:', error)
    emit('notification', { text: error.message || 'Failed to update template', color: 'error' })
  }
}

const handleDeleteTemplate = async (template) => {
  try {
    await emit('confirmDelete', {
      title: 'Delete Task Template',
      message: `Are you sure you want to delete the template "${template.display_name}"?`,
      warning:
        'This action cannot be undone. Existing tasks using this template will not be affected.',
      onConfirm: async () => {
        try {
          await deleteTemplate(template.id)
          emit('notification', { text: 'Task template deleted successfully!', color: 'success' })
        } catch (error) {
          emit('notification', {
            text: error.message || 'Failed to delete task template',
            color: 'error',
          })
        }
      },
    })
  } catch (error) {
    if (error.message && !error.message.includes('cancelled')) {
      console.error('Error deleting template:', error)
      emit('notification', { text: error.message || 'Failed to delete template', color: 'error' })
    }
  }
}

// Load templates on mount
onMounted(async () => {
  try {
    await loadTemplates()
  } catch (error) {
    console.error('Error loading templates:', error)
  }
})
</script>
