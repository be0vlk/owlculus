<template>
  <div class="d-flex flex-column ga-4">
    <div v-if="loading" class="d-flex justify-center">
      <v-progress-circular :size="50" :width="8" color="primary" indeterminate />
    </div>
    <v-alert v-else-if="error" type="error">
      {{ error }}
    </v-alert>
    <v-card v-else elevation="1" rounded="lg" class="d-flex flex-column">
      <v-card-title class="d-flex align-center justify-space-between flex-shrink-0">
        <span>Evidence</span>
        <div class="d-flex align-center ga-2">
          <div
            v-if="treeItems.length > 0 && selectedItems.length > 0"
            class="d-flex align-center ga-2"
          >
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
          <v-btn
            v-if="treeItems.length > 0 && userRole !== 'Analyst'"
            color="primary"
            size="small"
            variant="outlined"
            @click="showCreateFolder = true"
            prepend-icon="mdi-folder-plus"
          >
            Create Folder
          </v-btn>
        </div>
      </v-card-title>

      <v-card-text class="pa-4 flex-grow-1 overflow-y-auto evidence-container">
        <template v-if="treeItems.length === 0">
          <div class="text-center py-8">
            <v-icon icon="mdi-folder-open" size="64" color="grey-darken-1" class="mb-4" />
            <h3 class="text-h6 mb-2">No folders created yet</h3>
            <p class="text-body-2 text-medium-emphasis mb-4">
              Create your first folder to organize evidence
            </p>
            <div v-if="userRole !== 'Analyst'" class="d-flex flex-column align-center ga-3">
              <div class="d-flex ga-2">
                <v-btn :disabled="!caseId" color="primary" @click="showCreateFolder = true">
                  <v-icon start>mdi-folder-plus</v-icon>
                  Create Folder
                </v-btn>
                <v-btn
                  color="secondary"
                  variant="outlined"
                  @click="showTemplateSelection = true"
                  :disabled="!caseId"
                >
                  <v-icon start>mdi-folder-multiple</v-icon>
                  Use Template
                </v-btn>
              </div>
              <p class="text-caption text-medium-emphasis">
                Use a template to quickly create organized folder structures
              </p>
            </div>
          </div>
        </template>

        <template v-else>
          <v-treeview
            :key="`treeview-${treeItems.length}`"
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
                  :icon="getFolderIcon(open)"
                  :color="getFolderColor()"
                  @contextmenu.prevent="showContextMenu($event, item)"
                />
                <v-icon
                  v-else
                  :icon="getFileIcon(item)"
                  color="grey-darken-1"
                  class="cursor-pointer"
                  @contextmenu.prevent="showContextMenu($event, item)"
                  @dblclick="handleFileDoubleClick(item)"
                />
              </div>
            </template>

            <template v-slot:title="{ item }">
              <div
                class="tree-item-title-wrapper"
                :class="getDragClasses(item)"
                :draggable="!item.is_folder && userRole !== 'Analyst'"
                @dragstart="onDragStart($event, item)"
                @dragend="onDragEnd"
                @dragenter="onDragEnter($event, item)"
                @dragover="onDragOver($event, item)"
                @dragleave="onDragLeave($event, item)"
                @drop="onDrop($event, item)"
              >
                <span
                  class="tree-item-title"
                  :class="{ 'title-supported-file': hasFileAction(item) }"
                  @contextmenu.prevent="showContextMenu($event, item)"
                  @dblclick="handleFileDoubleClick(item)"
                >
                  {{ item.title }}
                </span>
              </div>
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
      </v-card-text>
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
    <RenameDialog v-model="showRename" :item="renameTargetItem" @renamed="handleItemRenamed" />

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
            <strong>{{ deleteTargetItem?.title }}</strong
            >?
          </p>
          <p v-if="deleteTargetItem?.is_folder" class="text-warning mt-2">
            <v-icon icon="mdi-alert" class="mr-1"></v-icon>
            This will also delete all contents within this folder.
          </p>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="grey" variant="text" @click="showDeleteConfirm = false"> Cancel </v-btn>
          <v-btn :loading="deleteLoading" color="error" variant="flat" @click="confirmDelete">
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
            Are you sure you want to delete <strong>{{ selectedItems.length }}</strong> selected
            items?
          </p>
          <p class="text-warning mt-2">
            <v-icon icon="mdi-alert" class="mr-1"></v-icon>
            This action cannot be undone. Folders will be deleted along with all their contents.
          </p>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="grey" variant="text" @click="showMassDeleteConfirm = false"> Cancel </v-btn>
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

    <!-- Template Selection Modal -->
    <evidence-template-selection-modal
      v-model="showTemplateSelection"
      :case-id="caseId"
      @template-applied="handleTemplateApplied"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { evidenceService } from '../services/evidence'
import CreateFolderDialog from './CreateFolderDialog.vue'
import FolderContextMenu from './FolderContextMenu.vue'
import EvidenceTemplateSelectionModal from './EvidenceTemplateSelectionModal.vue'
import RenameDialog from './RenameDialog.vue'
import { useFolderIcons } from '../composables/useFolderIcons'
import { useDragAndDrop } from '../composables/useDragAndDrop'
import {
  getFileTypeByExtension,
  getIconByExtension,
  SUPPORTED_PREVIEW_TYPES
} from '@/utils/fileExtension.js'

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
    default: 'Investigator',
  },
})

const emit = defineEmits([
  'download',
  'delete',
  'refresh',
  'upload-to-folder',
  'extract-metadata',
  'view-content',
  'evidence-moved',
])

// Composables
const { getFolderColor, getFolderIcon } = useFolderIcons()
const {
  handleDragStart,
  handleDragEnter,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  handleDragEnd,
  getDragClasses,
} = useDragAndDrop()

// Reactive data
const showCreateFolder = ref(false)
const showRename = ref(false)
const showDeleteConfirm = ref(false)
const showMassDeleteConfirm = ref(false)
const showTemplateSelection = ref(false)
const deleteLoading = ref(false)
const massDeleteLoading = ref(false)
const newFolderParent = ref(null)
const renameTargetItem = ref(null)
const deleteTargetItem = ref(null)
const openItems = ref([])

// Function to preserve open state during evidence updates
const preserveOpenState = () => {
  // Get currently open items from the treeview
  return [...openItems.value]
}

// Function to restore open state after evidence updates
const restoreOpenState = (savedOpenItems) => {
  openItems.value = savedOpenItems
}
const selectedItems = ref([])

// Context menu
const contextMenu = ref({
  show: false,
  activator: null,
  item: null,
})

// Computed

const treeItems = computed(() => {
  const items = []
  const itemMap = new Map()

  // First pass: create all items
  props.evidenceList.forEach((evidence) => {
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
      childCount: 0,
    }
    itemMap.set(evidence.id, item)
  })

  // Second pass: build hierarchy
  itemMap.forEach((item) => {
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
    return items
      .sort((a, b) => {
        if (a.is_folder && !b.is_folder) return -1
        if (!a.is_folder && b.is_folder) return 1
        return a.title.localeCompare(b.title)
      })
      .map((item) => ({
        ...item,
        children: item.children ? sortItems(item.children) : item.children,
      }))
  }

  return sortItems(items)
})

// Methods
const getFileIcon = (item) => {
  if (item.is_folder) return 'mdi-folder'

  const fileExtension = item.title.split('.').pop()

  return getIconByExtension(fileExtension)
}

function hasFileAction(item) {
  if (!item || !item.title) {
    return false;
  }

  const fileExtension = item.title.split('.').pop();
  const type = getFileTypeByExtension(fileExtension);

  return SUPPORTED_PREVIEW_TYPES.includes(type);
}

const handleFileDoubleClick = (item) => {
  if (hasFileAction(item)) {
    emit('view-content', item);
  }
}

const showContextMenu = (event, item) => {
  event.preventDefault()
  contextMenu.value = {
    show: true,
    activator: event.target,
    item,
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
    const itemsToDelete = props.evidenceList.filter((item) => selectedItems.value.includes(item.id))

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

const handleTemplateApplied = () => {
  showTemplateSelection.value = false
  emit('refresh')
}

// Drag and drop functionality
const handleMoveEvidence = async (draggedItem, targetFolder) => {
  // Store original evidence list and open state for potential rollback
  const originalEvidenceList = [...props.evidenceList]
  const savedOpenState = preserveOpenState()

  try {
    // Optimistically update the evidence list
    const updatedEvidenceList = moveItemOptimistically(
      draggedItem,
      targetFolder,
      props.evidenceList,
    )

    emit('evidence-moved', updatedEvidenceList, savedOpenState)
    await evidenceService.moveEvidence(draggedItem.id, targetFolder.id)

    return { success: true }
  } catch (error) {
    console.error('Failed to move evidence:', error)

    // Revert the optimistic update on failure
    emit('evidence-moved', originalEvidenceList, savedOpenState)

    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to move file',
    }
  }
}

// Helper function to optimistically move an item in the evidence list
const moveItemOptimistically = (draggedItem, targetFolder, evidenceList) => {
  const updatedList = evidenceList.map((item) => {
    if (item.id === draggedItem.id) {
      return {
        ...item,
        parent_folder_id: targetFolder.id,
      }
    }
    return item
  })

  return updatedList
}

const onDragStart = (event, item) => {
  return handleDragStart(event, item, props.userRole)
}

const onDragEnter = (event, item) => {
  if (item.is_folder) {
    handleDragEnter(event, item, props.userRole)
  }
}

const onDragOver = (event, item) => {
  if (item.is_folder) {
    handleDragOver(event, item, props.userRole)
  }
}

const onDragLeave = (event, item) => {
  if (item.is_folder) {
    handleDragLeave(event, item)
  }
}

const onDrop = async (event, item) => {
  if (item.is_folder) {
    const result = await handleDrop(event, item, props.userRole, handleMoveEvidence)

    if (!result.success && result.error) {
      console.error('Drop failed:', result.error)
    }
  }
}

const onDragEnd = () => {
  handleDragEnd()
}

// Watch for evidence list changes to maintain open state
watch(
  () => props.evidenceList,
  () => {
    // Maintain open folders
  },
  { deep: true },
)

// Expose methods to parent component
defineExpose({
  restoreOpenState,
  preserveOpenState,
})
</script>

<style scoped>
.tree-item-title {
  cursor: pointer;
  user-select: none;
}

.tree-item-title:hover {
  text-decoration: underline;
}

.title-supported-file {
  color: rgb(var(--v-theme-success));
  font-weight: 500;
}

.title-supported-file:hover {
  color: rgb(var(--v-theme-success-darken-1));
  text-decoration: underline;
}

.cursor-pointer {
  cursor: pointer;
}

.evidence-container {
  max-height: 60vh;
  min-height: 200px;
}

/* Responsive adjustments */
@media (max-width: 599px) {
  .evidence-container {
    max-height: 50vh;
  }
}

@media (min-width: 1280px) {
  .evidence-container {
    max-height: 70vh;
  }
}

:deep(.v-treeview-item) {
  border-radius: 4px;
  margin-bottom: 2px;
}

:deep(.v-treeview-item:hover) {
  background-color: rgb(var(--v-theme-on-surface), 0.05);
}

/* Drag and Drop Styles */
.evidence-dragging {
  opacity: 0.5;
  background-color: rgb(var(--v-theme-primary), 0.1);
  border: 2px dashed rgb(var(--v-theme-primary));
  border-radius: 4px;
}

.evidence-drag-over {
  background-color: rgb(var(--v-theme-success), 0.15);
  border: 2px solid rgb(var(--v-theme-success));
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(var(--v-theme-success), 0.3);
}

.evidence-invalid-drop {
  background-color: rgb(var(--v-theme-error), 0.1);
  border: 2px dashed rgb(var(--v-theme-error));
  border-radius: 4px;
}

.draggable-item {
  cursor: grab;
}

.draggable-item:active {
  cursor: grabbing;
}

/* Enhanced drag feedback for tree items */
:deep(.v-treeview-item.evidence-dragging) {
  opacity: 0.5;
  transform: scale(0.98);
  transition: all 0.2s ease;
}

:deep(.v-treeview-item.evidence-drag-over) {
  background-color: rgb(var(--v-theme-success), 0.1) !important;
  border-left: 4px solid rgb(var(--v-theme-success));
  padding-left: 8px;
  transition: all 0.2s ease;
}

:deep(.v-treeview-item.evidence-invalid-drop) {
  background-color: rgb(var(--v-theme-error), 0.1) !important;
  border-left: 4px solid rgb(var(--v-theme-error));
  padding-left: 8px;
}

/* Drag ghost styling */
.drag-ghost {
  background: white;
  border: 1px solid #ccc;
  border-radius: 4px;
  padding: 8px 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-size: 14px;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 200px;
}

/* Folder icon highlighting for valid drop targets */
.v-icon.drop-target-highlight {
  color: rgb(var(--v-theme-success)) !important;
  transform: scale(1.1);
  transition: all 0.2s ease;
}

/* Tree item title wrapper */
.tree-item-title-wrapper {
  width: 100%;
  display: flex;
  align-items: center;
  padding: 2px 4px;
  border-radius: 4px;
}

.tree-item-title-wrapper[draggable='true'] {
  cursor: grab;
}

.tree-item-title-wrapper[draggable='true']:active {
  cursor: grabbing;
}
</style>
