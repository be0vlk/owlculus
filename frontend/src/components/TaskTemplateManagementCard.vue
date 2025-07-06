<template>
  <v-card class="mb-6" variant="outlined">
    <v-card-title class="d-flex align-center pa-4 bg-surface">
      <v-icon icon="mdi-clipboard-text" color="primary" size="large" class="me-3" />
      <div class="flex-grow-1">
        <div class="text-h6 font-weight-bold">Task Templates</div>
        <div class="text-body-2 text-medium-emphasis">
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
        <div class="text-h6 text-medium-emphasis mb-2">No Task Templates</div>
        <div class="text-body-2 text-medium-emphasis mb-4">
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
            <th>Template</th>
            <th>Category</th>
            <th>Custom Fields</th>
            <th>Status</th>
            <th>Created By</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="template in sortedTemplates" :key="template.id">
            <td>
              <div>
                <div class="font-weight-medium">{{ template.display_name }}</div>
                <div class="text-caption text-medium-emphasis">{{ template.name }}</div>
              </div>
            </td>
            <td>
              <v-chip size="small" variant="tonal">
                {{ template.category }}
              </v-chip>
            </td>
            <td>
              <v-chip size="small" variant="tonal" color="info">
                {{ getFieldCount(template) }} fields
              </v-chip>
            </td>
            <td>
              <v-chip size="small" :color="template.is_active ? 'success' : 'grey'" variant="tonal">
                {{ template.is_active ? 'Active' : 'Inactive' }}
              </v-chip>
            </td>
            <td>
              <div v-if="template.creator" class="text-body-2">
                {{ template.creator.username }}
              </div>
              <div v-else class="text-caption text-medium-emphasis">System</div>
            </td>
            <td>
              <div class="d-flex align-center" style="gap: 8px">
                <v-btn
                  color="primary"
                  size="small"
                  variant="outlined"
                  icon
                  @click="openEditDialog(template)"
                  :disabled="saving || deleting"
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
    <v-dialog v-model="showAddDialog" max-width="800" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon icon="mdi-plus" class="me-3" />
          Add Task Template
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <TaskTemplateForm
            ref="addFormRef"
            v-model="newTemplateForm"
            :validate-template-name="validateTemplateName"
            :validate-display-name="validateDisplayName"
            :validate-description="validateDescription"
            :validate-category="validateCategory"
          />
        </v-card-text>

        <v-divider />

        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn :disabled="saving" variant="text" @click="closeAddDialog">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="saving" @click="handleCreateTemplate">
            Create Template
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Edit Template Dialog -->
    <v-dialog v-model="showEditDialog" max-width="800" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon icon="mdi-pencil" class="me-3" />
          Edit Task Template - {{ editingTemplate?.display_name }}
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <TaskTemplateForm
            ref="editFormRef"
            v-model="editTemplateForm"
            :is-edit="true"
            :validate-template-name="validateTemplateName"
            :validate-display-name="validateDisplayName"
            :validate-description="validateDescription"
            :validate-category="validateCategory"
          />
        </v-card-text>

        <v-divider />

        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn :disabled="saving" variant="text" @click="closeEditDialog">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="saving" @click="handleUpdateTemplate">
            Update Template
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useTaskTemplates } from '@/composables/useTaskTemplates'
import TaskTemplateForm from './TaskTemplateForm.vue'

const emit = defineEmits(['notification', 'confirmDelete'])

// Form refs
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
        await deleteTemplate(template.id)
        emit('notification', { text: 'Task template deleted successfully!', color: 'success' })
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

<style scoped>
.admin-dashboard-table :deep(.v-data-table__tr:hover) {
  background-color: rgb(var(--v-theme-primary), 0.04) !important;
}

.admin-dashboard-table :deep(.v-data-table__td) {
  padding: 12px 16px !important;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.08) !important;
}

.admin-dashboard-table :deep(.v-data-table__th) {
  padding: 16px !important;
  font-weight: 600 !important;
  color: rgb(var(--v-theme-on-surface), 0.87) !important;
  border-bottom: 2px solid rgb(var(--v-theme-on-surface), 0.12) !important;
}
</style>
