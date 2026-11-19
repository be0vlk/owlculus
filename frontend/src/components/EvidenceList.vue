<template>
  <div class="d-flex flex-column ga-4">
    <div v-if="loading" class="d-flex justify-center">
      <v-progress-circular :size="50" :width="8" color="primary" indeterminate />
    </div>
    <v-alert v-else-if="error" type="error">
      {{ error }}
    </v-alert>
    <v-card v-else elevation="1" rounded="lg" class="d-flex flex-column">
      <v-card-title class="d-flex align-center justify-space-between flex-shrink-0 flex-wrap ga-2">
        <span>Evidence</span>
        <div class="d-flex align-center flex-wrap ga-2">
          <div
            v-if="treeItems.length > 0 && selectedItems.length > 0"
            class="d-flex align-center flex-wrap ga-2"
          >
            <span class="text-body-small">{{ selectedItems.length }} selected</span>
            <v-btn
              v-if="userRole !== 'Analyst'"
              color="error"
              size="small"
              variant="outlined"
              @click="deleteSelected"
              prepend-icon="mdi-delete"
            >
              Delete Selected
            </v-btn>
          </div>
          <v-btn
            v-if="treeItems.length > 0 && userRole !== 'Analyst'"
            color="on-surface"
            size="small"
            variant="outlined"
            @click="openCreateFolder(null)"
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
            <h3 class="text-title-large mb-2">No folders created yet</h3>
            <p class="text-body-medium text-medium-emphasis mb-4">
              Create your first folder to organize evidence
            </p>
            <div v-if="userRole !== 'Analyst'" class="d-flex flex-column align-center ga-3">
              <div class="d-flex flex-wrap justify-center ga-2">
                <v-btn :disabled="!caseId" color="primary" @click="openCreateFolder(null)">
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
              <p class="text-body-small text-medium-emphasis">
                Use a template to quickly create organized folder structures
              </p>
            </div>
          </div>
        </template>

        <template v-else>
          <v-treeview
            :items="treeItems"
            v-model:opened="openItems"
            aria-label="Case evidence"
            open-on-click
            fluid
            slim
            item-value="id"
            item-title="title"
            item-children="children"
            density="compact"
            :return-object="false"
          >
            <template v-slot:title="{ item, isOpen }">
              <div class="evidence-row-content">
                <div
                  class="tree-item-title-wrapper"
                  :class="{
                    'evidence-dragging': draggedId === item.id,
                    'evidence-drag-over': dropTargetId === item.id,
                  }"
                  :draggable="!item.is_folder && userRole !== 'Analyst'"
                  @dragstart="
                    ((draggedId = item.id), $event.dataTransfer.setData('text/plain', item.title))
                  "
                  @dragend="draggedId = dropTargetId = null"
                  @dragover="canDrop(item) && ($event.preventDefault(), (dropTargetId = item.id))"
                  @dragleave="
                    !$event.currentTarget.contains($event.relatedTarget) && (dropTargetId = null)
                  "
                  @drop.prevent="moveTo(item)"
                >
                  <div class="d-flex align-center flex-wrap ga-2">
                    <v-checkbox-btn
                      :aria-label="`Select ${item.title}`"
                      @click.stop
                      :model-value="selectedItems.includes(item.id)"
                      @update:model-value="toggleSelection(item.id)"
                      density="compact"
                      hide-details
                    />
                    <v-icon
                      v-if="item.is_folder"
                      :icon="isOpen ? 'mdi-folder-open' : 'mdi-folder'"
                      color="purple-darken-1"
                      @contextmenu.prevent="showContextMenu($event, item)"
                    />
                    <v-icon
                      v-else
                      :icon="getFileIcon(item)"
                      color="grey-darken-1"
                      class="cursor-pointer"
                      @contextmenu.prevent="showContextMenu($event, item)"
                      @dblclick="viewContent(item)"
                    />
                  </div>
                  <span
                    class="tree-item-title"
                    :class="{ 'title-supported-file': hasFileAction(item) }"
                    @contextmenu.prevent="showContextMenu($event, item)"
                    @dblclick="viewContent(item)"
                  >
                    {{ item.title }}
                  </span>
                </div>
                <div class="evidence-item-actions d-flex flex-wrap align-center ga-1">
                  <v-btn
                    v-if="!item.is_folder && hasFileAction(item)"
                    size="x-small"
                    variant="text"
                    icon="mdi-eye"
                    :aria-label="`Preview ${item.title}`"
                    @click.stop="viewContent(item)"
                  />
                  <v-btn
                    size="x-small"
                    variant="text"
                    icon="mdi-dots-vertical"
                    :aria-label="`Actions for ${item.title}`"
                    @click.stop="showContextMenu($event, item)"
                  />
                  <v-chip v-if="item.children?.length" size="x-small" variant="tonal" color="grey">
                    {{ item.children.length }}
                  </v-chip>

                  <v-btn
                    v-if="!item.is_folder && item.evidence_type === 'file'"
                    size="x-small"
                    variant="text"
                    icon="mdi-download"
                    :aria-label="`Download ${item.title}`"
                    @click.stop="$emit('download', item)"
                  />

                  <v-btn
                    v-if="userRole !== 'Analyst'"
                    size="x-small"
                    variant="text"
                    icon="mdi-delete"
                    :aria-label="`Delete ${item.title}`"
                    color="error"
                    @click.stop="deleteItem(item)"
                  />
                </div>
              </div>
            </template>
          </v-treeview>
        </template>
      </v-card-text>
    </v-card>

    <v-alert v-if="actionError" type="error">{{ actionError }}</v-alert>
    <p v-if="moveStatus" role="status" class="text-body-medium">{{ moveStatus }}</p>

    <FolderContextMenu
      v-model="contextMenu.show"
      :activator="contextMenu.activator"
      :item="contextMenu.item"
      :user-role="userRole"
      @create-subfolder="openCreateFolder($event.id)"
      @upload-files="$emit('upload-to-folder', $event)"
      @rename="openRename"
      @delete="deleteItem"
      @extract-metadata="$emit('extract-metadata', $event)"
    />

    <CreateFolderDialog
      v-model="showCreateFolder"
      :case-id="caseId"
      :parent-folder-id="newFolderParent"
      @folder-created="$emit('refresh')"
    />

    <RenameDialog v-model="showRename" :item="renameTargetItem" @renamed="$emit('refresh')" />

    <ConfirmationDialog ref="confirmDialog" />

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
import { getErrorMessage } from '@/utils/errorMessage'
import ConfirmationDialog from './ConfirmationDialog.vue'
import CreateFolderDialog from './CreateFolderDialog.vue'
import FolderContextMenu from './FolderContextMenu.vue'
import EvidenceTemplateSelectionModal from './EvidenceTemplateSelectionModal.vue'
import RenameDialog from './RenameDialog.vue'
import {
  getFileTypeByExtension,
  getIconByExtension,
  SUPPORTED_PREVIEW_TYPES,
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
  'refresh',
  'upload-to-folder',
  'extract-metadata',
  'view-content',
  'evidence-moved',
])

const actionError = ref('')
const moveStatus = ref('')
const showCreateFolder = ref(false)
const showRename = ref(false)
const showTemplateSelection = ref(false)
const confirmDialog = ref(null)
const newFolderParent = ref(null)
const renameTargetItem = ref(null)
const openItems = ref([])
const selectedItems = ref([])
// Only files are draggable, so a drag can never move a folder into its own subtree.
const draggedId = ref(null)
const dropTargetId = ref(null)

const contextMenu = ref({
  show: false,
  activator: null,
  item: null,
})

const treeItems = computed(() => {
  const itemMap = new Map(
    props.evidenceList.map((evidence) => [
      evidence.id,
      { ...evidence, children: evidence.is_folder ? [] : undefined },
    ]),
  )
  const roots = []
  for (const item of itemMap.values()) {
    ;(itemMap.get(item.parent_folder_id)?.children ?? roots).push(item)
  }
  // Folders first, then by title.
  const order = (a, b) => !!b.is_folder - !!a.is_folder || a.title.localeCompare(b.title)
  for (const item of itemMap.values()) item.children?.sort(order)
  return roots.sort(order)
})

const getFileIcon = (item) => getIconByExtension(item.title.split('.').pop())

function hasFileAction(item) {
  const type = getFileTypeByExtension(item?.title?.split('.').pop())
  return SUPPORTED_PREVIEW_TYPES.includes(type)
}

const viewContent = (item) => {
  if (hasFileAction(item)) emit('view-content', item)
}

const showContextMenu = (event, item) => {
  event.preventDefault()
  contextMenu.value = {
    show: true,
    activator: event.currentTarget,
    item,
  }
}

const openCreateFolder = (parentId) => {
  newFolderParent.value = parentId
  showCreateFolder.value = true
}

const openRename = (item) => {
  renameTargetItem.value = item
  showRename.value = true
}

const toggleSelection = (itemId) => {
  const index = selectedItems.value.indexOf(itemId)
  if (index > -1) {
    selectedItems.value.splice(index, 1)
  } else {
    selectedItems.value.push(itemId)
  }
}

const deleteItems = async (items, label) => {
  try {
    await confirmDialog.value.confirmDelete(label)
  } catch {
    return
  }
  actionError.value = ''
  let deleted = 0
  try {
    for (const item of items) {
      await (item.is_folder
        ? evidenceService.deleteFolder(item.id)
        : evidenceService.deleteEvidence(item.id))
      deleted++
    }
  } catch (error) {
    actionError.value = getErrorMessage(error, 'Failed to delete evidence')
  }
  // Refreshing drops deleted ids from the selection; failed ones stay selected for a retry.
  if (deleted) emit('refresh')
}

const deleteItem = (item) => {
  const title = `"${item.title}"`
  deleteItems([item], item.is_folder ? `${title} and all its contents` : title)
}

const deleteSelected = () => {
  const items = props.evidenceList.filter((item) => selectedItems.value.includes(item.id))
  const label = `${items.length} selected items (folders with all their contents)`
  deleteItems(items, label)
}

const handleTemplateApplied = () => {
  showTemplateSelection.value = false
  emit('refresh')
}

const canDrop = (folder) => {
  const dragged = props.evidenceList.find((item) => item.id === draggedId.value)
  return folder.is_folder && !!dragged && dragged.parent_folder_id !== folder.id
}

const moveTo = async (folder) => {
  const id = draggedId.value
  draggedId.value = dropTargetId.value = null
  if (!id) return

  actionError.value = ''
  moveStatus.value = 'Moving evidence…'
  const original = props.evidenceList
  emit(
    'evidence-moved',
    original.map((item) => (item.id === id ? { ...item, parent_folder_id: folder.id } : item)),
  )
  try {
    await evidenceService.updateEvidence(id, { parentFolderId: folder.id })
    moveStatus.value = `Evidence moved to ${folder.title}`
  } catch (error) {
    emit('evidence-moved', original)
    moveStatus.value = ''
    actionError.value = getErrorMessage(error, 'Failed to move evidence')
  }
}

watch(
  () => props.evidenceList,
  () => {
    const ids = new Set(props.evidenceList.map((item) => item.id))
    openItems.value = openItems.value.filter((id) => ids.has(id))
    selectedItems.value = selectedItems.value.filter((id) => ids.has(id))
  },
)
</script>

<style scoped>
.evidence-row-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  white-space: normal;
}

.evidence-item-actions {
  max-width: 100%;
}

.tree-item-title {
  flex: 1;
  min-width: 0;
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
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}

.evidence-container {
  max-height: 60vh;
  min-height: 200px;
}

@media (width <= 599px) {
  .evidence-container {
    max-height: 50vh;
  }
}

@media (width >= 1280px) {
  .evidence-container {
    max-height: 70vh;
  }
}

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
  box-shadow: 0 2px 8px rgb(var(--v-theme-success), 0.3);
}

.tree-item-title-wrapper {
  width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
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
