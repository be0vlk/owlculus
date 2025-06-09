<template>
  <div class="folder-editor">
    <div class="folder-row">
      <div class="folder-content">
        <div class="folder-icon">
          <v-icon 
            :icon="expanded ? 'mdi-folder-open' : 'mdi-folder'" 
            :color="level === 0 ? 'blue-darken-1' : 'blue-lighten-1'"
            size="small"
          />
        </div>
        
        <div class="folder-fields flex-grow-1">
          <v-text-field
            v-model="localFolder.name"
            placeholder="Folder name"
            variant="outlined"
            density="compact"
            hide-details
            class="folder-name-field"
            @blur="updateFolder"
          />
          
          <v-text-field
            v-model="localFolder.description"
            placeholder="Description (optional)"
            variant="outlined"
            density="compact"
            hide-details
            class="folder-desc-field"
            @blur="updateFolder"
          />
        </div>

        <div class="folder-actions">
          <v-btn
            @click="toggleExpanded"
            v-if="hasSubfolders"
            icon
            size="x-small"
            variant="text"
            :color="expanded ? 'primary' : 'default'"
          >
            <v-icon :icon="expanded ? 'mdi-chevron-down' : 'mdi-chevron-right'" />
          </v-btn>
          
          <v-btn
            @click="addSubfolder"
            icon="mdi-folder-plus"
            size="x-small"
            variant="text"
            color="primary"
            class="ml-1"
          />
          
          <v-btn
            @click="deleteFolder"
            icon="mdi-delete"
            size="x-small"
            variant="text"
            color="error"
            class="ml-1"
          />
        </div>
      </div>
    </div>

    <div v-if="expanded && hasSubfolders" class="subfolders-container">
      <folder-editor
        v-for="(subfolder, index) in localFolder.subfolders"
        :key="`subfolder-${level}-${index}`"
        :folder="subfolder"
        :level="level + 1"
        :path="[...path, index]"
        @update="updateSubfolder(index, $event)"
        @delete="deleteSubfolder(index)"
        @add-subfolder="addSubfolderToChild(index, $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  folder: {
    type: Object,
    required: true
  },
  level: {
    type: Number,
    default: 0
  },
  path: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update', 'delete', 'add-subfolder'])

const localFolder = ref({ ...props.folder })
const expanded = ref(true)

const hasSubfolders = computed(() => {
  return localFolder.value.subfolders && localFolder.value.subfolders.length > 0
})

const updateFolder = () => {
  emit('update', { ...localFolder.value })
}

const deleteFolder = () => {
  emit('delete')
}

const addSubfolder = () => {
  if (!localFolder.value.subfolders) {
    localFolder.value.subfolders = []
  }
  localFolder.value.subfolders.push({
    name: 'New Subfolder',
    description: '',
    subfolders: []
  })
  expanded.value = true
  updateFolder()
}

const updateSubfolder = (index, updatedSubfolder) => {
  localFolder.value.subfolders[index] = updatedSubfolder
  updateFolder()
}

const deleteSubfolder = (index) => {
  localFolder.value.subfolders.splice(index, 1)
  updateFolder()
}

const addSubfolderToChild = (childIndex, path) => {
  emit('add-subfolder', [childIndex, ...path])
}

const toggleExpanded = () => {
  expanded.value = !expanded.value
}

watch(() => props.folder, (newFolder) => {
  localFolder.value = { ...newFolder }
}, { deep: true })
</script>

<style scoped>
.folder-editor {
  margin-bottom: 8px;
}

.folder-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.folder-content {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  min-height: 40px;
}

.folder-icon {
  display: flex;
  align-items: center;
  height: 40px;
  padding-top: 8px;
}

.folder-fields {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: flex-start;
}

.folder-name-field {
  min-width: 200px;
  max-width: 300px;
}

.folder-desc-field {
  min-width: 250px;
  max-width: 400px;
}

.folder-actions {
  display: flex;
  align-items: center;
  height: 40px;
  gap: 4px;
  padding-top: 4px;
}

.subfolders-container {
  margin-left: 24px;
  padding-left: 16px;
  border-left: 2px solid rgba(var(--v-theme-outline), 0.2);
  margin-top: 8px;
}

@media (max-width: 768px) {
  .folder-fields {
    flex-direction: column;
    width: 100%;
  }
  
  .folder-name-field,
  .folder-desc-field {
    min-width: 100%;
    max-width: 100%;
  }
}
</style>