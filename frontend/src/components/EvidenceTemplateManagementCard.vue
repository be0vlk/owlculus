<template>
  <v-card :elevation="0" variant="flat">
    <v-card-title class="d-flex flex-wrap align-center ga-3 pa-4">
      <div class="flex-grow-1">
        <h2 class="text-title-large font-weight-bold">Evidence folders</h2>
        <p class="text-body-medium text-medium-emphasis mb-0">
          Configure folder structures for each investigation type
        </p>
      </div>
      <v-btn
        size="small"
        color="primary"
        prepend-icon="mdi-content-save"
        :loading="saving"
        :disabled="saving || loading || !!error"
        @click="saveTemplates"
        >Save Changes</v-btn
      >
    </v-card-title>
    <!-- Loading state -->
    <div v-if="loading" class="pa-6">
      <v-skeleton-loader type="table-row@3" />
    </div>

    <!-- Error state -->
    <v-alert v-else-if="error" :text="error" class="ma-4" type="error" variant="tonal">
      <template v-slot:append>
        <v-btn size="small" variant="text" @click="loadTemplates">Retry</v-btn>
      </template>
    </v-alert>

    <v-alert v-if="saveError" :text="saveError" class="ma-4" type="error" variant="tonal" />

    <!-- Success notification -->
    <v-alert v-if="saveSuccess" class="ma-4" closable type="success" variant="tonal">
      Templates saved successfully!
    </v-alert>

    <!-- Main content -->
    <div v-if="!loading && !error">
      <!-- Tabs section with proper padding -->
      <div class="pa-4 pb-0">
        <v-tabs v-model="activeTab" bg-color="surface" class="mb-4">
          <v-tab
            v-for="(template, templateKey) in templates"
            :key="templateKey"
            :value="templateKey"
          >
            {{ template.name }}
          </v-tab>
        </v-tabs>
      </div>

      <v-divider />

      <!-- Tab content with consistent padding -->
      <div class="pa-4">
        <v-window v-model="activeTab">
          <v-window-item
            v-for="(template, templateKey) in templates"
            :key="templateKey"
            :value="templateKey"
          >
            <div class="template-editor">
              <div class="d-flex align-center justify-space-between mb-4">
                <div class="text-title-large font-weight-bold">Folder Structure</div>
                <v-btn
                  prepend-icon="mdi-folder-plus"
                  size="small"
                  variant="outlined"
                  @click="addRootFolder(templateKey)"
                >
                  Add Folder
                </v-btn>
              </div>

              <div v-if="template.folders && template.folders.length > 0" class="folders-container">
                <folder-editor
                  v-for="(folder, index) in template.folders"
                  :key="`${templateKey}-${index}`"
                  :folder="folder"
                  :level="0"
                  @delete="deleteFolder(templateKey, index)"
                  @update="updateFolder(templateKey, index, $event)"
                />
              </div>

              <div v-else class="empty-template text-center py-8">
                <v-icon class="mb-2" color="grey-lighten-1" icon="mdi-folder-outline" size="48" />
                <div class="text-title-large font-weight-medium mb-2">No Folder Structure</div>
                <p class="text-body-medium text-medium-emphasis mb-4">
                  No folders configured for this template. Click "Add Folder" to get started.
                </p>
              </div>
            </div>
          </v-window-item>
        </v-window>
      </div>
    </div>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { systemService } from '@/services/system'
import FolderEditor from './FolderEditor.vue'

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const saveError = ref('')
const saveSuccess = ref(false)
const activeTab = ref('Company')
const templates = ref({})

const loadTemplates = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await systemService.getEvidenceFolderTemplates()
    templates.value = response.templates || {}

    // Set default active tab if templates exist
    const templateKeys = Object.keys(templates.value)
    if (templateKeys.length > 0) {
      activeTab.value = templateKeys[0]
    }
  } catch (err) {
    error.value = 'Failed to load templates'
    console.error('Error loading templates:', err)
  } finally {
    loading.value = false
  }
}

const saveTemplates = async () => {
  saving.value = true
  saveSuccess.value = false
  saveError.value = ''
  try {
    await systemService.updateEvidenceFolderTemplates(templates.value)
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (err) {
    saveError.value = 'Failed to save templates'
    console.error('Error saving templates:', err)
  } finally {
    saving.value = false
  }
}

const addRootFolder = (templateKey) => {
  if (!templates.value[templateKey].folders) {
    templates.value[templateKey].folders = []
  }
  templates.value[templateKey].folders.push({
    name: 'New Folder',
    description: '',
    subfolders: [],
  })
}

const updateFolder = (templateKey, index, updatedFolder) => {
  templates.value[templateKey].folders[index] = updatedFolder
}

const deleteFolder = (templateKey, index) => {
  templates.value[templateKey].folders.splice(index, 1)
}

onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
.template-editor {
  max-width: 100%;
}

.folders-container {
  border: 1px solid rgb(var(--v-theme-on-surface), 0.08);
  border-radius: 8px;
  padding: 16px;
  background-color: rgb(var(--v-theme-surface));
}

.empty-template {
  border: 1px dashed rgb(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  background-color: rgb(var(--v-theme-surface));
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
</style>
