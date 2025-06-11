<template>
  <v-card class="mb-6" variant="outlined">
    <v-expansion-panels v-model="expansionPanel" variant="accordion">
      <v-expansion-panel>
        <v-expansion-panel-title class="pa-4 bg-surface">
          <div class="d-flex align-center w-100">
            <v-icon icon="mdi-folder-multiple" color="primary" size="large" class="me-3" />
            <div class="flex-grow-1">
              <div class="text-h6 font-weight-bold">Evidence Folder Templates</div>
              <div class="text-body-2 text-medium-emphasis">Configure folder structures for different types of investigations</div>
            </div>
            <v-btn
              v-if="expansionPanel === 0"
              @click.stop="saveTemplates"
              color="primary"
              variant="flat"
              prepend-icon="mdi-content-save"
              :disabled="saving"
              :loading="saving"
              class="me-3"
            >
              Save Changes
            </v-btn>
          </div>
        </v-expansion-panel-title>
        
        <v-expansion-panel-text class="pa-0">
      <!-- Loading state -->
      <div v-if="loading" class="pa-6">
        <v-skeleton-loader type="table-row@3" />
      </div>

      <!-- Error state -->
      <v-alert
        v-else-if="error"
        type="error"
        variant="tonal"
        class="ma-4"
        :text="error"
      >
        <template v-slot:append>
          <v-btn @click="loadTemplates" size="small" variant="text">Retry</v-btn>
        </template>
      </v-alert>

      <!-- Success notification -->
      <v-alert v-if="saveSuccess" type="success" variant="tonal" class="ma-4" closable>
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
                  <div class="text-h6 font-weight-bold">Folder Structure</div>
                  <v-btn
                    @click="addRootFolder(templateKey)"
                    size="small"
                    color="primary"
                    variant="outlined"
                    prepend-icon="mdi-folder-plus"
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
                    @update="updateFolder(templateKey, index, $event)"
                    @delete="deleteFolder(templateKey, index)"
                    @add-subfolder="addSubfolder(templateKey, index, $event)"
                  />
                </div>

                <div v-else class="empty-template text-center py-8">
                  <v-icon icon="mdi-folder-outline" size="48" color="grey-lighten-1" class="mb-2" />
                  <div class="text-h6 font-weight-medium mb-2">No Folder Structure</div>
                  <p class="text-body-2 text-medium-emphasis mb-4">
                    No folders configured for this template. Click "Add Folder" to get started.
                  </p>
                </div>
              </div>
            </v-window-item>
          </v-window>
        </div>
      </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { systemService } from '@/services/system'
import FolderEditor from './FolderEditor.vue'

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const saveSuccess = ref(false)
const activeTab = ref('Company')
const templates = ref({})
const expansionPanel = ref() // Start collapsed (undefined means collapsed)

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
  error.value = ''
  try {
    await systemService.updateEvidenceFolderTemplates(templates.value)
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (err) {
    error.value = 'Failed to save templates'
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
    subfolders: []
  })
}

const updateFolder = (templateKey, index, updatedFolder) => {
  templates.value[templateKey].folders[index] = updatedFolder
}

const deleteFolder = (templateKey, index) => {
  templates.value[templateKey].folders.splice(index, 1)
}

const addSubfolder = (templateKey, parentIndex, path) => {
  // Navigate to the correct subfolder array using the path
  let current = templates.value[templateKey].folders[parentIndex]
  for (let i = 0; i < path.length; i++) {
    current = current.subfolders[path[i]]
  }
  
  if (!current.subfolders) {
    current.subfolders = []
  }
  current.subfolders.push({
    name: 'New Subfolder',
    description: '',
    subfolders: []
  })
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