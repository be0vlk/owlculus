<template>
  <v-card :elevation="0" variant="flat">
    <v-card-title class="operations-heading d-flex flex-wrap ga-3 align-center pa-4 bg-surface">
      <div class="flex-grow-1">
        <h2 class="text-title-large font-weight-bold">Task templates</h2>
        <div class="text-body-medium text-medium-emphasis">
          Manage reusable task templates for standardized workflows
        </div>
      </div>
      <v-btn
        size="small"
        color="primary"
        prepend-icon="mdi-plus"
        @click="openDialog()"
        :disabled="loading"
      >
        Add Template
      </v-btn>
    </v-card-title>

    <v-divider />

    <v-card-text class="pa-0">
      <div v-if="loading" class="pa-6">
        <v-skeleton-loader type="table-row@5" />
      </div>

      <v-alert v-else-if="error" :text="error" class="ma-4" type="error" variant="tonal" />

      <div v-else-if="!sortedTemplates.length" class="pa-8 text-center">
        <v-icon icon="mdi-clipboard-off" size="64" color="grey-darken-1" class="mb-4" />
        <div class="text-title-large text-medium-emphasis mb-2">No Task Templates</div>
        <div class="text-body-medium text-medium-emphasis mb-4">
          Create task templates to standardize your investigation workflows
        </div>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="openDialog()">
          Create Your First Template
        </v-btn>
      </div>

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
                  size="small"
                  variant="outlined"
                  icon
                  @click="openDialog(template)"
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

    <v-dialog
      :aria-label="editing ? 'Edit Task Template' : 'Add Task Template'"
      v-model="showDialog"
      max-width="800"
      persistent
    >
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon :icon="editing ? 'mdi-pencil' : 'mdi-plus'" class="me-3" />
          {{ editing ? `Edit Task Template - ${editing.display_name}` : 'Add Task Template' }}
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <TaskTemplateForm
            :id="formId"
            ref="formRef"
            v-model="draft"
            :disabled="saving"
            :is-edit="!!editing"
            :existing-names="editing ? [] : templates.map((t) => t.name)"
            @submit="saveTemplate"
          />
        </v-card-text>

        <v-divider />

        <v-card-actions class="pa-4 flex-wrap">
          <v-spacer />
          <v-btn :disabled="saving" variant="text" @click="showDialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="saving" type="submit" :form="formId">
            {{ editing ? 'Update Template' : 'Create Template' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { computed, onMounted, ref, useId } from 'vue'
import { taskService } from '@/services/task'
import { getErrorMessage } from '@/utils/errorMessage'
import TaskTemplateForm from './TaskTemplateForm.vue'

const emit = defineEmits(['notification', 'confirmDelete'])

const formId = useId()
const formRef = ref(null)
const loading = ref(true)
const saving = ref(false)
const deleting = ref(false)
const error = ref('')
const templates = ref([])
const showDialog = ref(false)
const editing = ref(null)

const blankTemplate = () => ({
  name: '',
  display_name: '',
  description: '',
  category: '',
  is_active: true,
  definition_json: { fields: [] },
})
const draft = ref(blankTemplate())

const sortedTemplates = computed(() =>
  [...templates.value].sort(
    (a, b) => a.category.localeCompare(b.category) || a.display_name.localeCompare(b.display_name),
  ),
)

const getFieldCount = (template) => template.definition_json?.fields?.length || 0

const notify = (text, color) => emit('notification', { text, color })

function openDialog(template = null) {
  editing.value = template
  if (template) {
    const { name, display_name, description, category, is_active, definition_json } = template
    draft.value = {
      name,
      display_name,
      description,
      category,
      is_active,
      // Rows are reactive proxies, which structuredClone rejects.
      definition_json: JSON.parse(JSON.stringify(definition_json || { fields: [] })),
    }
  } else {
    draft.value = blankTemplate()
  }
  showDialog.value = true
}

async function saveTemplate() {
  if (saving.value || !(await formRef.value?.validate())) return
  const id = editing.value?.id
  saving.value = true
  try {
    if (id) {
      const updated = await taskService.updateTemplate(id, draft.value)
      templates.value = templates.value.map((t) => (t.id === id ? updated : t))
    } else {
      templates.value.push(await taskService.createCustomTemplate(draft.value))
    }
    showDialog.value = false
    notify(`Task template ${id ? 'updated' : 'created'} successfully!`, 'success')
  } catch (err) {
    console.error('Error saving template:', err)
    notify(getErrorMessage(err, `Failed to ${id ? 'update' : 'create'} template`), 'error')
  } finally {
    saving.value = false
  }
}

function handleDeleteTemplate(template) {
  emit('confirmDelete', {
    title: 'Delete Task Template',
    message: `Are you sure you want to delete the template "${template.display_name}"?`,
    warning:
      'This action cannot be undone. Existing tasks using this template will not be affected.',
    onConfirm: async () => {
      deleting.value = true
      try {
        await taskService.deleteTemplate(template.id)
        templates.value = templates.value.filter((t) => t.id !== template.id)
        notify('Task template deleted successfully!', 'success')
      } catch (err) {
        notify(getErrorMessage(err, 'Failed to delete task template'), 'error')
      } finally {
        deleting.value = false
      }
    },
  })
}

onMounted(async () => {
  try {
    templates.value = await taskService.getTemplates(true)
  } catch (err) {
    console.error('Error loading templates:', err)
    error.value = getErrorMessage(err, 'Failed to load templates')
  } finally {
    loading.value = false
  }
})
</script>
