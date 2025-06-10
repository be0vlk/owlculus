<template>
  <v-dialog v-model="dialogOpen" max-width="600px" persistent>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span>Select Evidence Folder Template</span>
        <v-btn icon="mdi-close" variant="text" @click="closeDialog" />
      </v-card-title>

      <v-card-text>
        <div v-if="loading" class="text-center py-4">
          <v-progress-circular indeterminate />
          <p class="mt-2">Loading templates...</p>
        </div>

        <div v-else-if="error" class="text-center py-4">
          <v-alert type="error" class="mb-4">{{ error }}</v-alert>
          <v-btn @click="loadTemplates" color="primary">Retry</v-btn>
        </div>

        <div v-else>
          <p class="text-body-2 text-medium-emphasis mb-4">
            Choose a predefined folder structure to organize your evidence.
          </p>

          <v-select
            v-model="selectedTemplate"
            :items="templateOptions"
            item-title="text"
            item-value="value"
            label="Template"
            variant="outlined"
            class="mb-4"
          >
            <template v-slot:selection="{ item }">
              <span>{{ item.title }}</span>
            </template>
            <template v-slot:item="{ props, item }">
              <v-list-item v-bind="props">
                <v-list-item-title>{{ item.title }}</v-list-item-title>
                <v-list-item-subtitle>{{ item.raw.description }}</v-list-item-subtitle>
              </v-list-item>
            </template>
          </v-select>

          <div v-if="selectedTemplate && selectedTemplateData" class="mb-4">
            <v-card variant="outlined">
              <v-card-title class="text-subtitle-1">Preview</v-card-title>
              <v-card-text>
                <div class="text-caption text-medium-emphasis mb-2">
                  {{ selectedTemplateData.description }}
                </div>
                <div v-if="selectedTemplateData.folders && selectedTemplateData.folders.length > 0">
                  <div class="text-caption font-weight-medium mb-2">Folder Structure:</div>
                  <div class="template-preview">
                    <template-folder-tree :folders="selectedTemplateData.folders" />
                  </div>
                </div>
                <div v-else class="text-caption text-medium-emphasis">
                  <v-icon icon="mdi-information" size="small" class="mr-1" />
                  This template is empty. You can configure it in Admin settings.
                </div>
              </v-card-text>
            </v-card>
          </div>
        </div>
      </v-card-text>

      <v-card-actions class="px-6 pb-4">
        <v-spacer />
        <v-btn @click="closeDialog" variant="text">Cancel</v-btn>
        <v-btn
          @click="applyTemplate"
          color="primary"
          :disabled="!selectedTemplate || applying"
          :loading="applying"
        >
          Apply Template
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { systemService } from '@/services/system'
import { evidenceService } from '@/services/evidence'
import TemplateFolderTree from './TemplateFolderTree.vue'

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
    text: templates.value[key].name,
    title: templates.value[key].name,
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
  background-color: rgb(var(--v-theme-surface));
  padding: 12px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.875rem;
}
</style>