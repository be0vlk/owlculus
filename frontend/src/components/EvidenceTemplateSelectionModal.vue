<template>
  <v-dialog v-model="dialogOpen" max-width="600px" persistent>
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-surface">
        <v-icon icon="mdi-folder-multiple" color="primary" size="large" class="me-3" />
        <div class="flex-grow-1">
          <div class="text-h6 font-weight-bold">Select Evidence Folder Template</div>
          <div class="text-body-2 text-medium-emphasis">
            Choose a predefined folder structure to organize your evidence
          </div>
        </div>
        <v-btn icon="mdi-close" variant="text" @click="closeDialog" />
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-6">
        <div v-if="loading" class="text-center py-8">
          <v-progress-circular 
            size="64" 
            width="4" 
            color="primary" 
            indeterminate 
          />
          <div class="text-h6 mt-4">Loading templates...</div>
        </div>

        <div v-else-if="error" class="text-center py-8">
          <v-alert 
            type="error" 
            variant="tonal" 
            prominent 
            icon="mdi-alert-circle"
            class="mb-6"
          >
            <v-alert-title>Error Loading Templates</v-alert-title>
            {{ error }}
          </v-alert>
          <v-btn 
            @click="loadTemplates" 
            color="primary" 
            prepend-icon="mdi-refresh"
            variant="flat"
          >
            Retry
          </v-btn>
        </div>

        <div v-else>

          <v-select
            v-model="selectedTemplate"
            :items="templateOptions"
            item-title="name"
            item-value="value"
            label="Select Template"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-folder-template"
            class="mb-4"
            placeholder="Choose a folder template..."
          >
            <template v-slot:item="{ props, item }">
              <v-list-item 
                :key="item.value"
                :value="item.value"
                @click="props.onClick"
              >
                <template v-slot:prepend>
                  <v-icon icon="mdi-folder-multiple" :color="getFolderColor()" class="me-3" />
                </template>
                <v-list-item-title>{{ item.raw.name }}</v-list-item-title>
                <v-list-item-subtitle v-if="item.raw.description">
                  {{ item.raw.description }}
                </v-list-item-subtitle>
              </v-list-item>
            </template>
          </v-select>

          <div v-if="selectedTemplate && selectedTemplateData" class="mb-4">
            <v-card variant="outlined">
              <v-card-title class="d-flex align-center pa-4 bg-surface">
                <v-icon icon="mdi-eye" color="primary" class="me-2" />
                <span class="text-subtitle-1 font-weight-bold">Template Preview</span>
              </v-card-title>
              <v-divider />
              <v-card-text class="pa-4">
                <div v-if="selectedTemplateData.description" class="text-body-2 text-medium-emphasis mb-4">
                  {{ selectedTemplateData.description }}
                </div>
                <div v-if="selectedTemplateData.folders && selectedTemplateData.folders.length > 0">
                  <div class="text-subtitle-2 font-weight-bold mb-3 d-flex align-center">
                    <v-icon icon="mdi-folder-outline" size="small" class="me-2" />
                    Folder Structure
                  </div>
                  <div class="template-preview">
                    <template-folder-tree :folders="selectedTemplateData.folders" />
                  </div>
                </div>
                <div v-else>
                  <v-alert 
                    type="info" 
                    variant="tonal" 
                    density="compact"
                    icon="mdi-information"
                  >
                    This template is empty. You can configure it in Admin settings.
                  </v-alert>
                </div>
              </v-card-text>
            </v-card>
          </div>
        </div>
      </v-card-text>

      <v-divider />
      
      <ModalActions
        submit-text="Apply Template"
        submit-icon="mdi-check"
        :submit-disabled="!selectedTemplate || applying"
        :loading="applying"
        @cancel="closeDialog"
        @submit="applyTemplate"
      />
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { systemService } from '@/services/system'
import { evidenceService } from '@/services/evidence'
import TemplateFolderTree from './TemplateFolderTree.vue'
import { useFolderIcons } from '../composables/useFolderIcons'
import ModalActions from './ModalActions.vue'

const { getFolderColor } = useFolderIcons()

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  caseId: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['update:modelValue', 'template-applied'])

const loading = ref(false)
const error = ref('')
const applying = ref(false)
const templates = ref({})
const selectedTemplate = ref('')

const dialogOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const templateOptions = computed(() => {
  return Object.keys(templates.value).map(key => ({
    value: key,
    name: templates.value[key].name,
    description: templates.value[key].description
  }))
})

const selectedTemplateData = computed(() => {
  if (!selectedTemplate.value || !templates.value[selectedTemplate.value]) {
    return null
  }
  return templates.value[selectedTemplate.value]
})

const loadTemplates = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await systemService.getEvidenceFolderTemplates()
    templates.value = response.templates || {}
  } catch (err) {
    error.value = 'Failed to load templates'
    console.error('Error loading templates:', err)
  } finally {
    loading.value = false
  }
}

const applyTemplate = async () => {
  if (!selectedTemplate.value) return

  applying.value = true
  try {
    await evidenceService.applyFolderTemplate(props.caseId, selectedTemplate.value)
    emit('template-applied')
    closeDialog()
  } catch (err) {
    error.value = 'Failed to apply template'
    console.error('Error applying template:', err)
  } finally {
    applying.value = false
  }
}

const closeDialog = () => {
  selectedTemplate.value = ''
  error.value = ''
  dialogOpen.value = false
}

watch(dialogOpen, (newValue) => {
  if (newValue) {
    loadTemplates()
  }
})
</script>

<style scoped>
.template-preview {
  background-color: rgb(var(--v-theme-surface-variant), 0.3);
  border: 1px solid rgb(var(--v-theme-outline), 0.2);
  padding: 16px;
  border-radius: 8px;
  font-family: 'Roboto Mono', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
}
</style>