<!-- THROWAWAY content: shared sample data and local interactions keep comparisons fair. -->
<template>
  <div class="prototype-content">
    <section v-show="tab === 'entities'" aria-label="Entities workspace">
      <div class="content-heading">
        <div>
          <h2>
            Entities <span>{{ entities.length }}</span>
          </h2>
          <p>People, organizations, and infrastructure in this case.</p>
        </div>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="$emit('action', 'Add Entity')"
          >Add Entity</v-btn
        >
      </div>
      <div class="entity-controls">
        <v-text-field
          v-model="state.search"
          placeholder="Search entities…"
          aria-label="Search entities"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          hide-details
          clearable
        /><v-menu
          ><template #activator="{ props: menuProps }"
            ><v-btn v-bind="menuProps" variant="outlined" prepend-icon="mdi-download"
              >Export entities</v-btn
            ></template
          ><v-list
            ><v-list-item
              title="Export as CSV"
              @click="$emit('notify', 'Entity CSV export preview')" /><v-list-item
              title="Export as JSON"
              @click="$emit('notify', 'Entity JSON export preview')" /></v-list
        ></v-menu>
      </div>
      <v-chip-group v-model="state.entityTypes" multiple filter class="entity-filters"
        ><v-chip
          v-for="type in types"
          :key="type.value"
          :value="type.value"
          :prepend-icon="type.icon"
          variant="outlined"
          size="small"
          filter
          >{{ type.label }}</v-chip
        ></v-chip-group
      >
      <div v-if="state.selected.length" class="selection-toolbar">
        <span>{{ state.selected.length }} selected</span
        ><v-btn variant="text" color="error" size="small" @click="deleteIds = [...state.selected]"
          >Delete selected</v-btn
        ><v-btn variant="text" size="small" @click="state.selected = []">Clear selection</v-btn>
      </div>
      <v-data-table
        v-model="state.selected"
        :headers="entityHeaders"
        :items="filteredEntities"
        :items-per-page="10"
        :items-per-page-options="[10, 25, 50]"
        show-select
        hover
        class="prototype-entity-table"
        @click:row="(_, { item }) => $emit('inspect', item)"
      >
        <template #[`item.entity_type`]="{ item }"
          ><span class="entity-type"
            ><v-icon :icon="typeFor(item).icon" size="17" />{{ typeFor(item).label }}</span
          ></template
        >
        <template #[`item.name`]="{ item }"
          ><button class="entity-name" @click.stop="$emit('inspect', item)">
            {{ name(item) }}
          </button>
          <div v-if="item.data.email || item.data.website" class="entity-subtitle">
            {{ item.data.email || item.data.website }}
          </div></template
        >
        <template #[`item.description`]="{ item }"
          ><span class="entity-description">{{ item.data.description }}</span></template
        >
        <template #[`item.created_at`]="{ item }"
          ><span class="entity-date">{{
            new Date(item.created_at).toLocaleDateString('en-GB', {
              day: '2-digit',
              month: 'short',
            })
          }}</span></template
        >
        <template #[`item.actions`]="{ item }"
          ><div class="row-actions">
            <v-btn
              icon="mdi-eye-outline"
              variant="text"
              size="small"
              :aria-label="`View ${name(item)}`"
              @click.stop="$emit('inspect', item)"
            /><v-btn
              icon="mdi-delete-outline"
              variant="text"
              size="small"
              :aria-label="`Delete ${name(item)}`"
              @click.stop="deleteIds = [item.id]"
            /></div
        ></template>
        <template #no-data
          ><div class="empty-content">
            <v-icon icon="mdi-account-search-outline" size="40" class="mb-3" />
            <h3>No matching entities</h3>
            <p>Change the search or type filters, or add an entity.</p>
            <v-btn variant="text" @click="clearFilters">Clear filters</v-btn>
          </div></template
        >
      </v-data-table>
    </section>

    <section v-show="tab === 'evidence'" aria-label="Evidence workspace">
      <div class="content-heading">
        <div>
          <h2>
            Evidence <span>{{ files.length }}</span>
          </h2>
          <p>Collected material, organized with its source context.</p>
        </div>
        <v-btn color="primary" prepend-icon="mdi-upload" @click="$emit('action', 'Upload Evidence')"
          >Upload Evidence</v-btn
        >
      </div>
      <div class="evidence-layout">
        <aside class="folder-tree" aria-label="Evidence folders">
          <div class="folder-heading">
            Folders<v-btn
              icon="mdi-folder-plus-outline"
              variant="text"
              size="small"
              aria-label="Create folder"
              @click="newFolderOpen = true"
            />
          </div>
          <button :class="{ active: state.folder === null }" @click="state.folder = null">
            <v-icon size="19">mdi-folder-multiple-outline</v-icon>All evidence<span>{{
              files.length
            }}</span></button
          ><button
            v-for="folder in folders"
            :key="folder.id"
            :class="{ active: state.folder === folder.id }"
            @click="state.folder = folder.id"
          >
            <v-icon size="19">mdi-folder-outline</v-icon>{{ folder.title
            }}<span>{{ files.filter((file) => file.parent_folder_id === folder.id).length }}</span>
          </button>
        </aside>
        <div class="evidence-files">
          <div class="evidence-path">
            <strong>{{
              folders.find((folder) => folder.id === state.folder)?.title || 'All evidence'
            }}</strong
            ><v-btn
              v-if="state.folder"
              variant="text"
              size="small"
              prepend-icon="mdi-pencil-outline"
              @click="openRename"
              >Rename folder</v-btn
            >
          </div>
          <v-text-field
            v-model="state.evidenceSearch"
            aria-label="Search evidence"
            placeholder="Search evidence…"
            prepend-inner-icon="mdi-magnify"
            hide-details
            density="compact"
            class="mb-4"
          /><button
            v-for="file in visibleFiles"
            :key="file.id"
            class="evidence-file"
            @click="$emit('inspect', file)"
          >
            <v-icon color="primary" size="26">{{
              file.title.endsWith('.png') ? 'mdi-file-image-outline' : 'mdi-file-document-outline'
            }}</v-icon
            ><span
              ><strong>{{ file.title }}</strong
              ><small>{{ file.description }}</small></span
            ><span class="file-size">{{ Math.round(file.file_size / 1000) }} KB</span
            ><v-icon size="18">mdi-chevron-right</v-icon>
          </button>
          <div v-if="!visibleFiles.length" class="empty-content">No evidence in this view.</div>
        </div>
      </div>
    </section>

    <section v-show="tab === 'tasks'" aria-label="Tasks workspace">
      <div class="content-heading">
        <div>
          <h2>Tasks</h2>
          <p>Follow-up work for this investigation.</p>
        </div>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="$emit('action', 'Add Task')"
          >Add Task</v-btn
        >
      </div>
      <div class="task-list">
        <div v-for="task in state.tasks" :key="task.id" class="task-row">
          <v-checkbox
            v-model="task.done"
            :label="task.title"
            hide-details
            :class="{ 'task-complete': task.done }"
          /><span>{{ task.owner }}</span
          ><v-chip :color="task.done ? 'success' : undefined" variant="tonal" size="small">{{
            task.done ? 'Done' : 'To do'
          }}</v-chip>
        </div>
      </div>
    </section>

    <section v-show="tab === 'notes'" class="notes-workspace" aria-label="Notes workspace">
      <div class="content-heading">
        <div>
          <h2>Notes</h2>
          <p>Working observations and investigation context.</p>
        </div>
        <v-btn
          v-if="!state.editingNotes"
          color="primary"
          prepend-icon="mdi-pencil-outline"
          @click="state.editingNotes = true"
          >Edit Notes</v-btn
        >
        <div v-else class="note-actions">
          <v-btn variant="text" @click="cancelNotes">Cancel</v-btn
          ><v-btn color="primary" prepend-icon="mdi-content-save-outline" @click="saveNotes"
            >Save</v-btn
          >
        </div>
      </div>
      <div class="note-paper">
        <div class="note-status">
          <v-icon size="15">{{
            state.editingNotes ? 'mdi-circle-edit-outline' : 'mdi-check'
          }}</v-icon
          >{{
            state.editingNotes
              ? 'Editing · draft kept when you switch tabs'
              : 'All changes saved in this preview'
          }}
        </div>
        <NoteEditor
          v-model="state.notes"
          :case-id="caseId"
          :is-editing="state.editingNotes"
          save-mode="manual"
          variant="plain"
        />
      </div>
    </section>

    <section v-show="tab === 'runs'" aria-label="Runs workspace">
      <div class="content-heading">
        <div>
          <h2>Runs</h2>
          <p>
            {{
              canViewHunts
                ? 'Plugin and hunt history, together with their retained results.'
                : 'Plugin history and retained results for this case.'
            }}
          </p>
        </div>
        <div class="run-actions">
          <v-btn
            prepend-icon="mdi-refresh"
            variant="outlined"
            @click="$emit('notify', 'Sample history refreshed')"
            >Refresh history</v-btn
          >
          <v-btn
            v-if="canViewHunts"
            color="primary"
            prepend-icon="mdi-target"
            @click="$emit('notify', 'Browse Hunts would open the existing hunt catalog.')"
            >Browse Hunts</v-btn
          >
        </div>
      </div>
      <v-table class="runs-table"
        ><thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Input</th>
            <th>Status</th>
            <th>Started</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="run in runs" :key="run.key">
            <td>
              <strong>{{ run.display_name }}</strong>
            </td>
            <td>
              <span class="entity-type"
                ><v-icon
                  size="17"
                  :icon="run.run_type === 'Hunt' ? 'mdi-target' : 'mdi-puzzle-outline'"
                />{{ run.run_type }}</span
              >
            </td>
            <td>{{ run.parameters.domain }}</td>
            <td>
              <v-chip
                :color="run.status === 'failed' ? 'error' : 'success'"
                size="small"
                variant="tonal"
                >{{ run.status === 'completed' ? 'Completed' : 'Failed' }}</v-chip
              >
            </td>
            <td class="entity-date">
              {{
                new Date(run.created_at).toLocaleDateString('en-GB', {
                  day: 'numeric',
                  month: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                })
              }}
            </td>
            <td>
              <v-btn variant="text" size="small" @click="$emit('inspect', run)">View results</v-btn>
            </td>
          </tr>
        </tbody></v-table
      >
      <div v-if="!runs.length" class="empty-content">No runs for this case.</div>
      <p class="history-footer">{{ runs.length }} executions · History refreshes when requested</p>
    </section>

    <v-dialog
      :model-value="deleteIds.length > 0"
      max-width="440"
      aria-label="Delete sample entities"
      @update:model-value="deleteIds = []"
      ><v-card
        ><v-card-title class="pa-5"
          >Delete {{ deleteIds.length }} sample
          {{ deleteIds.length === 1 ? 'entity' : 'entities' }}?</v-card-title
        ><v-card-text>This only changes the in-memory preview.</v-card-text
        ><v-card-actions class="pa-5"
          ><v-spacer /><v-btn variant="text" @click="deleteIds = []">Cancel</v-btn
          ><v-btn color="error" @click="deleteSelected">Delete</v-btn></v-card-actions
        ></v-card
      ></v-dialog
    >
    <v-dialog v-model="newFolderOpen" max-width="440" aria-label="Create folder"
      ><v-card
        ><v-card-title class="pa-5">Create folder</v-card-title
        ><v-card-text
          ><v-text-field
            v-model="folderName"
            label="Folder name"
            hide-details
            autofocus /></v-card-text
        ><v-card-actions class="pa-5"
          ><v-btn variant="text" @click="newFolderOpen = false">Cancel</v-btn
          ><v-btn color="primary" :disabled="!folderName.trim()" @click="createFolder"
            >Create folder</v-btn
          ></v-card-actions
        ></v-card
      ></v-dialog
    >
    <v-dialog v-model="renameOpen" max-width="440" aria-label="Rename folder"
      ><v-card
        ><v-card-title class="pa-5">Rename folder</v-card-title
        ><v-card-text
          ><v-text-field
            v-model="folderRename"
            label="Folder name"
            hide-details
            autofocus /></v-card-text
        ><v-card-actions class="pa-5"
          ><v-btn variant="text" @click="renameOpen = false">Cancel</v-btn
          ><v-btn color="primary" :disabled="!folderRename.trim()" @click="renameFolder"
            >Save</v-btn
          ></v-card-actions
        ></v-card
      ></v-dialog
    >
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import NoteEditor from '@/components/NoteEditor.vue'
const props = defineProps({
  caseId: { type: Number, required: true },
  tab: { type: String, required: true },
  state: { type: Object, required: true },
  entities: { type: Array, default: () => [] },
  evidence: { type: Array, default: () => [] },
  runs: { type: Array, default: () => [] },
  canViewHunts: { type: Boolean, default: false },
})
const emit = defineEmits(['action', 'inspect', 'notify', 'remove'])
// Shared mutable state is intentional in this throwaway: switching layout keeps the comparison state.
const state = props.state
function clearFilters() {
  state.search = ''
  state.entityTypes = []
}
function cancelNotes() {
  state.notes = state.savedNotes
  state.editingNotes = false
}
function saveNotes() {
  state.savedNotes = state.notes
  state.editingNotes = false
  emit('notify', 'Notes saved in this preview')
}
function createFolder() {
  state.extraFolders = [
    ...(state.extraFolders || []),
    { id: Date.now(), title: folderName.value, children: [] },
  ]
  folderName.value = ''
  newFolderOpen.value = false
}
function renameFolder() {
  state.folderNames = { ...state.folderNames, [state.folder]: folderRename.value }
  renameOpen.value = false
}
function openRename() {
  folderRename.value = folders.value.find((folder) => folder.id === state.folder)?.title
  renameOpen.value = true
}
const deleteIds = ref([])
const newFolderOpen = ref(false)
const folderName = ref('')
const renameOpen = ref(false)
const folderRename = ref('')
const types = [
  { value: 'person', label: 'Person', icon: 'mdi-account-outline' },
  { value: 'company', label: 'Company', icon: 'mdi-office-building-outline' },
  { value: 'domain', label: 'Domain', icon: 'mdi-web' },
  { value: 'ip_address', label: 'IP Address', icon: 'mdi-ip-network-outline' },
  { value: 'vehicle', label: 'Vehicle', icon: 'mdi-car-outline' },
]
const name = (item) =>
  item.data.domain ||
  item.data.name ||
  item.data.ip_address ||
  [item.data.first_name, item.data.last_name].filter(Boolean).join(' ') ||
  [item.data.make, item.data.model].join(' ')
const typeFor = (item) => types.find((type) => type.value === item.entity_type) || types[0]
const entityHeaders = [
  { title: 'Type', key: 'entity_type', width: 138 },
  { title: 'Name', key: 'name', value: name },
  { title: 'Description', key: 'description', sortable: false },
  { title: 'Created', key: 'created_at', width: 92 },
  { title: '', key: 'actions', sortable: false, width: 86 },
]
const filteredEntities = computed(() =>
  props.entities.filter(
    (item) =>
      (!state.entityTypes.length || state.entityTypes.includes(item.entity_type)) &&
      `${name(item)} ${item.data.description || ''}`
        .toLowerCase()
        .includes((state.search || '').toLowerCase()),
  ),
)
const folders = computed(() =>
  [...props.evidence, ...(state.extraFolders || [])].map((folder) => ({
    ...folder,
    title: state.folderNames?.[folder.id] || folder.title,
  })),
)
const files = computed(() => [
  ...props.evidence.flatMap((folder) => folder.children || []),
  ...state.addedEvidence,
])
const visibleFiles = computed(() =>
  files.value.filter(
    (file) =>
      (!state.folder || file.parent_folder_id === state.folder) &&
      file.title.toLowerCase().includes((state.evidenceSearch || '').toLowerCase()),
  ),
)
function deleteSelected() {
  deleteIds.value.forEach((id) => emit('remove', id))
  deleteIds.value = []
  state.selected = []
}
</script>

<style scoped>
.prototype-content {
  min-width: 0;
}

.task-row > span {
  font-size: 12px;
  opacity: 0.65;
}

.prototype-content h2,
.prototype-content h3,
.prototype-content p {
  margin: 0;
}

.prototype-content :where(button:not(.v-btn)) {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-family: inherit;
}

.content-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 22px;
}

.content-heading h2 {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
}

.content-heading :where(h2 span) {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface), 0.6);
  padding: 2px 7px;
  border-radius: 5px;
  background: rgb(var(--v-theme-on-surface), 0.06);
  vertical-align: middle;
}

.content-heading p {
  font-size: 12px;
  margin-top: 4px;
  opacity: 0.65;
}

.content-heading :deep(.v-btn),
.entity-controls :deep(.v-btn) {
  font-size: 12px;
  letter-spacing: 0;
  height: 36px;
  flex-shrink: 0;
}

.entity-controls {
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

.entity-controls > .v-input {
  max-width: 390px;
}

.entity-controls :deep(input),
.evidence-files :deep(input) {
  font-size: 13px;
}

.entity-filters {
  margin: 8px 0 14px;
}

.entity-filters :deep(.v-chip) {
  border-color: rgb(var(--v-border-color), 0.18);
  font-size: 12px;
}

.prototype-entity-table {
  border-top: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
}

.prototype-entity-table :deep(th) {
  font-size: 11px;
  font-weight: 600 !important;
  height: 40px !important;
  color: rgb(var(--v-theme-on-surface), 0.6);
}

.prototype-entity-table :deep(td) {
  height: 62px !important;
  font-size: 13px;
}

.prototype-entity-table :deep(.v-table__wrapper) {
  overflow-x: auto;
}

.prototype-entity-table :deep(table) {
  min-width: 780px;
}

.prototype-entity-table :deep(.v-data-table-footer) {
  font-size: 12px;
  padding-top: 18px;
}

.entity-type {
  display: flex;
  align-items: center;
  gap: 7px;
  white-space: nowrap;
  font-size: 12px;
  opacity: 0.75;
}

.entity-name {
  text-align: left;
  font-weight: 500;
  font-size: 13px;
  overflow-wrap: anywhere;
}

.entity-name:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 4px;
}

.entity-subtitle {
  font-size: 11px;
  opacity: 0.6;
  margin-top: 2px;
}

.entity-description {
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface), 0.7);
  display: block;
  max-width: 640px;
  min-width: 150px;
}

.entity-date {
  white-space: nowrap;
  font-size: 12px;
  opacity: 0.7;
}

.row-actions {
  display: flex;
}

.row-actions :deep(.v-icon) {
  font-size: 18px;
  opacity: 0.65;
}

.selection-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 12px;
  font-size: 12px;
  background: rgb(var(--v-theme-primary), 0.08);
}

.evidence-layout {
  display: grid;
  grid-template-columns: 215px minmax(0, 1fr);
  border-top: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
}

.folder-tree {
  border-right: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
  padding: 16px 16px 20px 0;
}

.folder-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  margin: 0 8px 12px;
}

.folder-tree > button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  text-align: left;
  padding: 12px 10px;
  border-radius: 6px;
  font-size: 12px;
  margin-bottom: 3px;
}

.folder-tree > button :where(span) {
  margin-left: auto;
  opacity: 0.6;
  font-size: 11px;
}

.folder-tree > button.active {
  background: rgb(var(--v-theme-primary), 0.1);
  font-weight: 600;
}

.evidence-files {
  padding: 20px 0 0 24px;
  min-width: 0;
}

.evidence-path {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-size: 13px;
}

.evidence-file {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 19px 0;
  border-bottom: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
  text-align: left;
  width: 100%;
}

.evidence-file > span:first-of-type {
  flex: 1;
  min-width: 0;
}

.evidence-file strong {
  display: block;
  font-weight: 500;
  font-size: 13px;
  overflow-wrap: anywhere;
}

.evidence-file small {
  display: block;
  opacity: 0.6;
  font-size: 11px;
  margin-top: 4px;
}

.file-size {
  font-size: 11px;
  opacity: 0.6;
  white-space: nowrap;
}

.empty-content {
  text-align: center;
  padding: 60px 20px;
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface), 0.65);
}

.empty-content h3 {
  font-size: 16px;
  margin-bottom: 8px;
}

.task-list {
  border-top: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
}

.task-row {
  display: flex;
  align-items: center;
  gap: 24px;
  border-bottom: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
  padding: 10px 0;
}

.task-row .v-checkbox {
  flex: 1;
}

.task-row :deep(.v-label) {
  font-size: 13px;
}

.task-complete :deep(.v-label) {
  text-decoration: line-through;
  opacity: 0.5;
}

.notes-workspace {
  max-width: 960px;
  margin-inline: auto;
}

.note-paper {
  border-top: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
  padding-top: 14px;
}

.note-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  opacity: 0.65;
  margin: 0 12px 20px;
}

.note-actions {
  display: flex;
  gap: 8px;
}

.note-paper :deep(.ProseMirror) {
  max-width: 760px;
  min-height: 340px;
  margin-inline: auto;
  line-height: 1.8;
}

.note-paper :deep(.note-editor-wrapper) {
  border: 0;
}

.runs-table {
  border-top: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
}

.run-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.runs-table :deep(table) {
  min-width: 640px;
}

.runs-table :deep(td) {
  height: 64px !important;
  font-size: 13px;
}

.runs-table :deep(th) {
  font-size: 11px;
}

.history-footer {
  font-size: 11px;
  opacity: 0.6;
  margin-top: 20px;
}

@media (width <= 700px) {
  .content-heading {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 12px;
  }

  .content-heading p {
    max-width: 280px;
  }

  .entity-controls {
    flex-wrap: wrap;
  }

  .entity-controls > .v-input {
    flex-basis: 100%;
    max-width: none;
  }

  .entity-controls > .v-btn {
    margin-left: auto;
  }

  .evidence-layout {
    display: block;
  }

  .folder-tree {
    border-right: 0;
    border-bottom: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
    padding-right: 0;
  }

  .evidence-files {
    padding-left: 0;
  }

  .file-size {
    display: none;
  }

  .task-row {
    flex-wrap: wrap;
    gap: 8px;
  }

  .task-row .v-checkbox {
    flex-basis: 100%;
  }

  .task-row > span {
    padding-left: 40px;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    transition: none !important;
  }
}
</style>
