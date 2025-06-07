<template>
  <div class="d-flex flex-column ga-4">
    <div v-if="loading" class="d-flex justify-center">
      <v-progress-circular
        indeterminate
        :size="50"
        :width="8"
        color="primary"
      />
    </div>
    <v-alert v-else-if="error" type="error">
      {{ error }}
    </v-alert>
    <v-card v-else elevation="1" rounded="lg">
      <v-card-title class="d-flex align-center justify-space-between">
        <span>Evidence</span>
        <div v-if="treeItems.length > 0 && selectedItems.length > 0" class="d-flex align-center ga-2">
          <span class="text-caption">{{ selectedItems.length }} selected</span>
          <v-btn
            v-if="userRole !== 'Analyst'"
            color="error"
            size="small"
            variant="outlined"
            @click="showMassDeleteConfirm = true"
            prepend-icon="mdi-delete"
          >
            Delete Selected
          </v-btn>
        </div>
      </v-card-title>
      
      <div class="pa-4">
        <template v-if="treeItems.length === 0">
          <div class="text-center py-8">
            <v-icon icon="mdi-folder-open" size="64" color="grey-darken-1" class="mb-4" />
            <h3 class="text-h6 mb-2">No folders created yet</h3>
            <p class="text-body-2 text-medium-emphasis mb-4">
              Create your first folder to organize evidence
            </p>
            <v-btn
              v-if="userRole !== 'Analyst'"
              color="primary"
              @click="showCreateFolder = true"
              :disabled="!caseId"
            >
              <v-icon start>mdi-folder-plus</v-icon>
              Create Folder
            </v-btn>
          </div>
        </template>
        
        <template v-else>
          <v-treeview
            :items="treeItems"
            :open="openItems"
            item-value="id"
            item-title="title"
            item-children="children"
            density="compact"
            :return-object="false"
          >
            <template v-slot:prepend="{ item, open }">
              <div class="d-flex align-center ga-2">
                <v-checkbox-btn
                  :model-value="selectedItems.includes(item.id)"
                  @update:model-value="toggleSelection(item.id)"
                  density="compact"
                  hide-details
                />
                <v-icon 
                  v-if="item.is_folder"
                  :icon="open ? 'mdi-folder-open' : 'mdi-folder'"
                  color="blue-darken-1"
                  @contextmenu.prevent="showContextMenu($event, item)"
                />
                <v-icon 
                  v-else
                  :icon="getFileIcon(item)"
                  color="grey-darken-1"
                  @contextmenu.prevent="showContextMenu($event, item)"
                />
              </div>
            </template>
            
            <template v-slot:title="{ item }">
              <span 
                class="tree-item-title"
                @contextmenu.prevent="showContextMenu($event, item)"
              >
                {{ item.title }}
              </span>
            </template>
            
            <template v-slot:append="{ item }">
              <div class="d-flex align-center ga-1">
                <v-chip 
                  v-if="item.is_folder && item.childCount > 0"
                  size="x-small" 
                  variant="tonal"
                  color="grey"
                >
                  {{ item.childCount }}
                </v-chip>
                
                <v-btn
                  v-if="!item.is_folder && item.evidence_type === 'file'"
                  size="x-small"
                  variant="text"
                  icon="mdi-download"
                  @click.stop="$emit('download', item)"
                />
                
                <v-btn
                  v-if="userRole !== 'Analyst'"
                  size="x-small"
                  variant="text"
                  icon="mdi-delete"
                  color="error"
                  @click.stop="deleteItem(item)"
                />
              </div>
            </template>
          </v-treeview>
        </template>
      </div>
    </v-card>
    
    <!-- Context Menu -->
    <FolderContextMenu
      v-model="contextMenu.show"
      :activator="contextMenu.activator"
      :item="contextMenu.item"
      :user-role="userRole"
      @create-subfolder="createSubfolder"
      @upload-files="uploadToFolder"
      @rename="renameItem"
      @delete="deleteItem"
      @extract-metadata="extractMetadata"
    />
    
    <!-- Create Folder Dialog -->
    <CreateFolderDialog
      v-model="showCreateFolder"
      :case-id="caseId"
      :parent-folder-id="newFolderParent"
      @folder-created="handleFolderCreated"
    />
    
    <!-- Rename Dialog -->
    <RenameDialog
      v-model="showRename"
      :item="renameTargetItem"
      @renamed="handleItemRenamed"
    />
    
    <!-- Delete Confirmation -->
    <v-dialog v-model="showDeleteConfirm" max-width="500px">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-delete" color="error" class="mr-2"></v-icon>
          Confirm Delete
        </v-card-title>
        
        <v-card-text>
          <p>
            Are you sure you want to delete 
            <strong>{{ deleteTargetItem?.title }}</strong>?
          </p>
          <p v-if="deleteTargetItem?.is_folder" class="text-warning mt-2">
            <v-icon icon="mdi-alert" class="mr-1"></v-icon>
            This will also delete all contents within this folder.
          </p>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="grey" variant="text" @click="showDeleteConfirm = false">
            Cancel
          </v-btn>
          <v-btn 
            color="error" 
            variant="flat" 
            @click="confirmDelete"
            :loading="deleteLoading"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    
    
    <!-- Mass Delete Confirmation -->
    <v-dialog v-model="showMassDeleteConfirm" max-width="500px">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-delete-multiple" color="error" class="mr-2"></v-icon>
          Confirm Mass Delete
        </v-card-title>
        
        <v-card-text>
          <p>
            Are you sure you want to delete <strong>{{ selectedItems.length }}</strong> selected items?
          </p>
          <p class="text-warning mt-2">
            <v-icon icon="mdi-alert" class="mr-1"></v-icon>
            This action cannot be undone. Folders will be deleted along with all their contents.
          </p>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="grey" variant="text" @click="showMassDeleteConfirm = false">
            Cancel
          </v-btn>
          <v-btn 
            color="error" 
            variant="flat" 
            @click="confirmMassDelete"
            :loading="massDeleteLoading"
          >
            Delete All
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { evidenceService } from '../services/evidence'
import CreateFolderDialog from './CreateFolderDialog.vue'
import FolderContextMenu from './FolderContextMenu.vue'
import RenameDialog from './RenameDialog.vue'

const props = defineProps({
  evidenceList: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
  caseId: {
    type: Number,
    required: true,
  },
  userRole: {
    type: String,
    default: 'Investigator'
  }
})

const emit = defineEmits(['download', 'delete', 'refresh', 'upload-to-folder', 'extract-metadata'])

// Reactive data
const showCreateFolder = ref(false)
const showRename = ref(false)
const showDeleteConfirm = ref(false)
const showMassDeleteConfirm = ref(false)
const deleteLoading = ref(false)
const massDeleteLoading = ref(false)
const newFolderParent = ref(null)
const renameTargetItem = ref(null)
const deleteTargetItem = ref(null)
const openItems = ref([])
const selectedItems = ref([])

// Context menu
const contextMenu = ref({
  show: false,
  activator: null,
  item: null
})

// Computed


const treeItems = computed(() => {
  const items = []
  const itemMap = new Map()
  
  // First pass: create all items
  props.evidenceList.forEach(evidence => {
    const item = {
      id: evidence.id,
      title: evidence.title,
      is_folder: evidence.is_folder,
      evidence_type: evidence.evidence_type,
      category: evidence.category,
      file_hash: evidence.file_hash,
      parent_folder_id: evidence.parent_folder_id,
      folder_path: evidence.folder_path,
      children: evidence.is_folder ? [] : undefined, // Only folders have children
      childCount: 0
    }
    itemMap.set(evidence.id, item)
  })
  
  // Second pass: build hierarchy
  itemMap.forEach(item => {
    if (item.parent_folder_id && itemMap.has(item.parent_folder_id)) {
      const parent = itemMap.get(item.parent_folder_id)
      parent.children.push(item)
      parent.childCount++
    } else {
      items.push(item)
    }
  })
  
  // Sort items: folders first, then by title
  const sortItems = (items) => {
    return items.sort((a, b) => {
      if (a.is_folder && !b.is_folder) return -1
      if (!a.is_folder && b.is_folder) return 1
      return a.title.localeCompare(b.title)
    }).map(item => ({
      ...item,
      children: item.children ? sortItems(item.children) : item.children
    }))
  }
  
  return sortItems(items)
})

// Methods
const getFileIcon = (item) => {
  if (item.is_folder) return 'mdi-folder'
  
  const fileExtension = item.title.split('.').pop()?.toLowerCase()
  
  switch (fileExtension) {
    case 'pdf':
      return 'mdi-file-pdf-box'
    case 'doc':
    case 'docx':
      return 'mdi-file-word-box'
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
      return 'mdi-file-image-box'
    case 'mp4':
    case 'avi':
    case 'mov':
      return 'mdi-file-video-box'
    case 'mp3':
    case 'wav':
      return 'mdi-file-music-box'
    case 'txt':
      return 'mdi-file-document-outline'
    default:
      return 'mdi-file-document'
  }
}

const showContextMenu = (event, item) => {
  event.preventDefault()
  contextMenu.value = {
    show: true,
    activator: event.target,
    item
  }
}


const createSubfolder = (parentItem) => {
  newFolderParent.value = parentItem?.id || null
  showCreateFolder.value = true
}

const uploadToFolder = (folderItem) => {
  emit('upload-to-folder', folderItem)
}

const renameItem = (item) => {
  renameTargetItem.value = item
  showRename.value = true
}

const deleteItem = (item) => {
  deleteTargetItem.value = item
  showDeleteConfirm.value = true
}


const extractMetadata = (item) => {
  emit('extract-metadata', item)
}

const toggleSelection = (itemId) => {
  const index = selectedItems.value.indexOf(itemId)
  if (index > -1) {
    // Remove from selection
    selectedItems.value.splice(index, 1)
  } else {
    // Add to selection
    selectedItems.value.push(itemId)
  }
}


const handleFolderCreated = () => {
  emit('refresh')
}

const handleItemRenamed = () => {
  emit('refresh')
}

const confirmDelete = async () => {
  if (!deleteTargetItem.value) return
  
  deleteLoading.value = true
  
  try {
    if (deleteTargetItem.value.is_folder) {
      await evidenceService.deleteFolder(deleteTargetItem.value.id)
    } else {
      await evidenceService.deleteEvidence(deleteTargetItem.value.id)
    }
    
    emit('refresh')
    showDeleteConfirm.value = false
  } catch (error) {
    console.error('Delete error:', error)
  } finally {
    deleteLoading.value = false
  }
}

const confirmMassDelete = async () => {
  if (selectedItems.value.length === 0) return
  
  massDeleteLoading.value = true
  
  try {
    // Get the items to delete from the evidence list
    const itemsToDelete = props.evidenceList.filter(item => 
      selectedItems.value.includes(item.id)
    )
    
    // Delete each item
    for (const item of itemsToDelete) {
      if (item.is_folder) {
        await evidenceService.deleteFolder(item.id)
      } else {
        await evidenceService.deleteEvidence(item.id)
      }
    }
    
    // Clear selection and refresh
    selectedItems.value = []
    emit('refresh')
    showMassDeleteConfirm.value = false
  } catch (error) {
    console.error('Mass delete error:', error)
  } finally {
    massDeleteLoading.value = false
  }
}

// Watch for evidence list changes to maintain open state
watch(() => props.evidenceList, () => {
  // Maintain open folders
}, { deep: true })
</script>

<style scoped>
.tree-item-title {
  cursor: pointer;
  user-select: none;
}

.tree-item-title:hover {
  text-decoration: underline;
}

:deep(.v-treeview-item) {
  border-radius: 4px;
  margin-bottom: 2px;
}

:deep(.v-treeview-item:hover) {
  background-color: rgb(var(--v-theme-on-surface), 0.05);
}
</style>