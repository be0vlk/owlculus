<template>
  <BaseDashboard
    :title="caseData ? `Case: ${caseData.case_number}` : 'Case Details'"
    :loading="loading"
    :error="error"
  >
    <template #header-actions>
      <div v-if="caseData" class="d-flex align-center ga-4">
        <v-btn-group variant="outlined" divided>
          <v-btn
            color="white"
            prepend-icon="mdi-pencil"
            @click="showEditModal = true"
          >
            Edit Case
          </v-btn>
          <v-btn
            color="white"
            prepend-icon="mdi-account-plus"
            @click="showAddUserModal = true"
          >
            Add User
          </v-btn>
        </v-btn-group>
      </div>
    </template>

    <template #loading>
      <v-card variant="outlined" class="pa-8 mx-auto" max-width="400">
        <v-progress-circular
          size="64"
          width="4"
          color="primary"
          indeterminate
          class="mb-4 d-block mx-auto"
        />
        <div class="text-h6 text-center">Loading case...</div>
        <div class="text-body-2 text-medium-emphasis text-center">Please wait while we load your case data</div>
      </v-card>
    </template>

    <!-- Case Content -->
    <div v-if="caseData">
      <!-- Case Information Card -->
      <v-card class="mb-6" variant="outlined">
        <!-- Header -->
        <v-card-title class="d-flex align-center pa-4 bg-surface">
          <v-icon icon="mdi-information" color="primary" size="large" class="me-3" />
          <div class="flex-grow-1">
            <div class="text-h6 font-weight-bold">Case Information</div>
            <div class="text-body-2 text-medium-emphasis">Details and metadata for this investigation</div>
          </div>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-6">
          <v-row>
            <v-col cols="12" lg="8">
              <CaseDetail :case-data="caseData" :client="client" />
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- Case Tabs Card -->
      <v-card variant="outlined">
        <!-- Header -->
        <v-card-title class="d-flex align-center pa-4 bg-surface">
          <v-icon icon="mdi-tab" color="primary" size="large" class="me-3" />
          <div class="flex-grow-1">
            <div class="text-h6 font-weight-bold">Case Management</div>
            <div class="text-body-2 text-medium-emphasis">Manage entities, evidence, and notes</div>
          </div>
        </v-card-title>

        <v-divider />
            <CaseTabs
              :tabs="availableTabs"
            >
              <template #default="{ activeTab }">
                <!-- Entities Tab -->
                <div v-if="activeTab === 'entities'" class="pa-4">
                  <v-row class="mb-4" no-gutters>
                    <v-col cols="auto">
                      <v-btn
                        color="primary"
                        prepend-icon="mdi-plus"
                        @click="showNewEntityModal = true"
                      >
                        Add Entity
                      </v-btn>
                    </v-col>
                  </v-row>

                  <!-- Entity Data Table -->
                  <EntityDataTable
                    ref="entityTableRef"
                    :case-id="Number(route.params.id)"
                    :entity-service="entityServiceRef"
                    @view="showEntityDetails"
                    @edit="showEntityDetails"
                    @create="showNewEntityModal = true"
                    @deleted="handleEntityDeleted"
                  />
                </div>

                <!-- Evidence Tab -->
                <div v-else-if="activeTab === 'evidence'" class="pa-4">
                  <v-row class="mb-4" no-gutters>
                    <v-col cols="auto">
                      <v-btn
                        color="primary"
                        prepend-icon="mdi-upload"
                        @click="showUploadEvidenceModal = true"
                        :disabled="!hasFolders"
                      >
                        Upload Evidence
                      </v-btn>
                      <v-tooltip
                        v-if="!hasFolders"
                        activator="parent"
                        location="bottom"
                      >
                        Create a folder first to organize evidence
                      </v-tooltip>
                    </v-col>
                  </v-row>
                  <EvidenceList
                    ref="evidenceListRef"
                    :evidence-list="evidence"
                    :loading="loadingEvidence"
                    :error="evidenceError"
                    :case-id="Number(route.params.id)"
                    :user-role="userRole"
                    @download="handleDownloadEvidence"
                    @delete="handleDeleteEvidence"
                    @refresh="loadEvidence"
                    @upload-to-folder="handleUploadToFolder"
                    @extract-metadata="handleExtractMetadata"
                    @view-text-content="handleViewTextContent"
                    @view-image-content="handleViewImageContent"
                    @evidence-moved="handleEvidenceMoved"
                  />
                </div>

                <!-- Hunts Tab -->
                <div v-else-if="activeTab === 'hunts'" class="pa-4">
                  <div class="d-flex align-center justify-space-between mb-4">
                    <div>
                      <div class="text-h6">Hunt Executions</div>
                      <div class="text-body-2 text-medium-emphasis">
                        View and manage automated investigation workflows for this case
                      </div>
                    </div>
                    <v-btn
                      color="primary"
                      prepend-icon="mdi-target"
                      @click="$router.push('/hunts')"
                    >
                      Browse Hunts
                    </v-btn>
                  </div>

                  <!-- Hunt Executions List -->
                  <div v-if="caseHuntExecutions.length > 0">
                    <v-row>
                      <v-col
                        v-for="execution in caseHuntExecutions"
                        :key="execution.id"
                        cols="12"
                        md="6"
                        lg="4"
                      >
                        <v-card variant="outlined" hover @click="viewHuntExecution(execution.id)">
                          <v-card-title class="d-flex align-center pa-3">
                            <v-avatar :color="getHuntStatusColor(execution.status)" size="32" class="me-3">
                              <v-icon :icon="getHuntStatusIcon(execution.status)" color="white" size="small" />
                            </v-avatar>
                            <div class="flex-grow-1">
                              <div class="text-body-1 font-weight-medium">{{ getFormattedHuntTitle(execution) }}</div>
                              <div class="text-caption">{{ execution.hunt_category }}</div>
                            </div>
                            <v-chip :color="getHuntStatusColor(execution.status)" variant="flat" size="small">
                              {{ execution.status }}
                            </v-chip>
                          </v-card-title>
                          <v-card-text class="pa-3 pt-0">
                            <div class="d-flex align-center justify-space-between">
                              <div class="text-caption">
                                <v-icon icon="mdi-clock" size="small" class="me-1" />
                                {{ formatDateTime(execution.created_at) }}
                              </div>
                              <div class="text-caption">
                                Progress: {{ Math.round(execution.progress * 100) }}%
                              </div>
                            </div>
                          </v-card-text>
                        </v-card>
                      </v-col>
                    </v-row>
                  </div>

                  <!-- Empty State -->
                  <div v-else class="text-center pa-8">
                    <v-icon icon="mdi-target" size="64" color="grey" class="mb-4" />
                    <div class="text-h6 mb-2">No Hunt Executions</div>
                    <div class="text-body-2 text-medium-emphasis mb-4">
                      Start automated investigation workflows to gather evidence for this case
                    </div>
                    <v-btn color="primary" @click="$router.push('/hunts')">
                      Browse Available Hunts
                    </v-btn>
                  </div>
                </div>

                <!-- Notes Tab -->
                <div v-else-if="activeTab === 'notes'" class="pa-6">
                  <v-card variant="outlined">
                    <v-card-title class="d-flex align-center">
                      <v-icon start>mdi-note-text</v-icon>
                      Case Notes
                      <v-spacer />
                      <v-chip
                        :color="isEditingNotes ? 'warning' : 'primary'"
                        variant="tonal"
                        size="small"
                        class="me-3"
                      >
                        {{ isEditingNotes ? 'Editing' : 'View Mode' }}
                      </v-chip>
                    </v-card-title>
                    <v-divider />
                    <v-card-text class="pa-0">
                      <NoteEditor
                        v-model="caseData.notes"
                        :case-id="Number(route.params.id)"
                        :is-editing="isEditingNotes"
                        :save-mode="'manual'"
                        :variant="'plain'"
                        @update:modelValue="handleNotesUpdate"
                      />
                    </v-card-text>
                    <v-divider />
                    <v-card-actions class="pa-4">
                      <v-spacer />
                      <div v-if="!isEditingNotes">
                        <v-btn
                          color="primary"
                          variant="flat"
                          prepend-icon="mdi-pencil"
                          @click="startEditingNotes"
                        >
                          Edit Notes
                        </v-btn>
                      </div>
                      <div v-else class="d-flex ga-2">
                        <v-btn
                          variant="text"
                          @click="cancelEditingNotes"
                        >
                          Cancel
                        </v-btn>
                        <v-btn
                          color="primary"
                          variant="flat"
                          prepend-icon="mdi-content-save"
                          @click="saveNotes"
                          :loading="savingNotes"
                        >
                          Save
                        </v-btn>
                      </div>
                    </v-card-actions>
                  </v-card>
                </div>
              </template>
            </CaseTabs>
          </v-card>
        </div>
      </BaseDashboard>

    <!-- Modals -->
    <EditCaseModal
      v-if="caseData"
      :show="showEditModal"
      :case-data="caseData"
      @close="showEditModal = false"
      @case-updated="handleCaseUpdate"
    />

    <AddUserToCaseModal
      v-if="caseData"
      :show="showAddUserModal"
      :case-id="Number(route.params.id)"
      @close="showAddUserModal = false"
      @user-added="loadCaseData"
    />

    <NewEntityModal
      :show="showNewEntityModal"
      :case-id="route.params.id"
      @close="showNewEntityModal = false"
      @created="handleNewEntity"
    />

    <EntityDetailsModal
      v-if="selectedEntity"
      :show="showEntityDetailsModal"
      :entity="selectedEntity"
      :case-id="Number(route.params.id)"
      :existing-entities="entities"
      @close="showEntityDetailsModal = false"
      @edit="handleEditEntity"
      @viewEntity="showEntityDetails"
    />

    <UploadEvidenceModal
      v-if="showUploadEvidenceModal"
      :show="showUploadEvidenceModal"
      :case-id="Number(route.params.id)"
      :target-folder="uploadTargetFolder"
      @close="showUploadEvidenceModal = false; uploadTargetFolder = null"
      @uploaded="handleEvidenceUpload"
    />

    <MetadataModal
      v-model="showMetadataModal"
      :evidence-item="selectedEvidenceForMetadata"
      :metadata="extractedMetadata"
      :loading="loadingMetadata"
      :error="metadataError"
    />

    <TextContentModal
      v-model="showTextContentModal"
      :evidence-item="selectedEvidenceForTextContent"
      :content="textContent"
      :file-info="textFileInfo"
      :loading="loadingTextContent"
      :error="textContentError"
    />

    <ImageContentModal
      v-model="showImageContentModal"
      :evidence-item="selectedEvidenceForImageContent"
      :file-info="imageFileInfo"
      :loading="loadingImageContent"
      :error="imageContentError"
    />

    <!-- Entity Creation Success Dialog -->
    <v-dialog
      v-model="showEntityCreationSuccess"
      max-width="500px"
      persistent
    >
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon start color="success">mdi-check-circle</v-icon>
          Entity Created Successfully
        </v-card-title>

        <v-card-text>
          <p class="text-body-1 mb-4">
            Your entity <strong>{{ getEntityDisplayName(createdEntity) }}</strong> has been created successfully.
          </p>

          <p class="text-body-2 text-medium-emphasis">
            Would you like to open the entity details to add more information and edit its properties?
          </p>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn
            variant="text"
            @click="handleSkipEditEntity"
          >
            No, thanks
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            @click="handleEditNewEntity"
          >
            Yes, edit entity
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
</template>

<script setup>
import {computed, onMounted, ref} from 'vue';
import {useRoute, useRouter} from 'vue-router';
import {useAuthStore} from '../stores/auth';
import BaseDashboard from '../components/BaseDashboard.vue';
import CaseDetail from '../components/CaseDetail.vue';
import EntityDataTable from '../components/entities/EntityDataTable.vue';
import CaseTabs from '../components/CaseTabs.vue';
import EditCaseModal from '../components/EditCaseModal.vue';
import AddUserToCaseModal from '../components/AddUserToCaseModal.vue';
import NewEntityModal from '../components/NewEntityModal.vue';
import EntityDetailsModal from '../components/entities/EntityDetailsModal.vue';
import NoteEditor from '../components/NoteEditor.vue';
import EvidenceList from '../components/EvidenceList.vue';
import UploadEvidenceModal from '../components/UploadEvidenceModal.vue';
import MetadataModal from '../components/MetadataModal.vue';
import TextContentModal from '../components/TextContentModal.vue';
import ImageContentModal from '../components/ImageContentModal.vue';
import {caseService} from '../services/case';
import {clientService} from '../services/client';
import {entityService} from '../services/entity';
import {evidenceService} from '../services/evidence';
import {useHuntStore} from '../stores/huntStore.js';
import {formatHuntExecutionTitle} from '../utils/huntDisplayUtils';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const huntStore = useHuntStore();
const loading = ref(false);
const error = ref(null);
const caseData = ref(null);
const client = ref(null);
const entities = ref([]);
const entityTableRef = ref(null);
const evidenceListRef = ref(null);
const showEditModal = ref(false);
const showAddUserModal = ref(false);
const showNewEntityModal = ref(false);
const showEntityDetailsModal = ref(false);
const selectedEntity = ref(null);
const evidence = ref([]);
const loadingEvidence = ref(false);
const evidenceError = ref('');
const showUploadEvidenceModal = ref(false);
const uploadTargetFolder = ref(null);
const showEntityCreationSuccess = ref(false);
const createdEntity = ref(null);
const showMetadataModal = ref(false);
const selectedEvidenceForMetadata = ref(null);
const extractedMetadata = ref(null);
const loadingMetadata = ref(false);
const metadataError = ref('');

const showTextContentModal = ref(false);
const selectedEvidenceForTextContent = ref(null);
const textContent = ref('');
const textFileInfo = ref(null);
const loadingTextContent = ref(false);
const textContentError = ref('');

const showImageContentModal = ref(false);
const selectedEvidenceForImageContent = ref(null);
const imageFileInfo = ref(null);
const loadingImageContent = ref(false);
const imageContentError = ref('');

const isEditingNotes = ref(false);
const savingNotes = ref(false);
const originalNotes = ref('');
const entityServiceRef = entityService;

// Hunt-related reactive data
const caseHuntExecutions = ref([]);
const loadingHuntExecutions = ref(false);

const userRole = computed(() => authStore.user?.role || 'Analyst');

const availableTabs = computed(() => {
  const tabs = [
    { name: 'entities', label: 'Entities' },
    { name: 'evidence', label: 'Evidence' },
  ];

  // Add Hunts tab for non-analyst users
  if (userRole.value !== 'Analyst') {
    tabs.push({ name: 'hunts', label: 'Hunts' });
  }

  tabs.push({ name: 'notes', label: 'Notes' });

  return tabs;
});

const hasFolders = computed(() => {
  return evidence.value.some(item => item.is_folder);
});

function showEntityDetails(entity) {
  selectedEntity.value = entity;
  showEntityDetailsModal.value = true;
}

async function handleEditEntity(updatedEntity, createdAssociates = []) {
  const index = entities.value.findIndex((e) => e.id === updatedEntity.id);
  if (index !== -1) {
    entities.value[index] = { ...updatedEntity };
    if (selectedEntity.value?.id === updatedEntity.id) {
      selectedEntity.value = { ...updatedEntity };
    }

    if (createdAssociates.length > 0) {
      entities.value = [...entities.value, ...createdAssociates];
    }

    if (entityTableRef.value) {
      entityTableRef.value.refresh();
    }
  }
}

const handleCaseUpdate = (updatedCase) => {
  Object.assign(caseData.value, updatedCase);
};

const handleNotesUpdate = (notes) => {
  if (caseData.value) {
    caseData.value.notes = notes;
  }
};

const startEditingNotes = () => {
  originalNotes.value = caseData.value?.notes || '';
  isEditingNotes.value = true;
};

const cancelEditingNotes = () => {
  if (caseData.value) {
    caseData.value.notes = originalNotes.value;
  }
  isEditingNotes.value = false;
};

const saveNotes = async () => {
  if (!caseData.value) return;

  try {
    savingNotes.value = true;
    await caseService.updateCase(route.params.id, { notes: caseData.value.notes });
    originalNotes.value = caseData.value.notes;
    isEditingNotes.value = false;
  } catch (error) {
    console.error('Failed to save notes:', error);
  } finally {
    savingNotes.value = false;
  }
};

const handleNewEntity = (newEntity) => {
  entities.value = [...entities.value, newEntity];
  showEntityCreationSuccess.value = true;
  createdEntity.value = newEntity;

  if (entityTableRef.value) {
    entityTableRef.value.refresh();
  }
};

const handleEditNewEntity = () => {
  selectedEntity.value = createdEntity.value;
  showEntityDetailsModal.value = true;
  showEntityCreationSuccess.value = false;
  createdEntity.value = null;
};

const handleSkipEditEntity = () => {
  showEntityCreationSuccess.value = false;
  createdEntity.value = null;
};

const handleEntityDeleted = () => {
};


const loadClientData = async (clientId) => {
  try {
    const response = await clientService.getClient(clientId);
    client.value = response;
  } catch (err) {
    console.error('Error loading client:', err);
  }
};

const loadCaseData = async () => {
  try {
    loading.value = true;
    error.value = null;
    const data = await caseService.getCase(route.params.id);
    caseData.value = data;
    if (data.client_id) {
      await loadClientData(data.client_id);
    }
  } catch (err) {
    error.value = `Error loading case: ${err.message}`;
    console.error('Error loading case:', err);
  } finally {
    loading.value = false;
  }
};

// Entities are now handled by EntityDataTable component

const loadEvidence = async () => {
  if (!route.params.id) return;

  loadingEvidence.value = true;
  evidenceError.value = '';

  try {
    evidence.value = await evidenceService.getFolderTree(Number(route.params.id));
  } catch (error) {
    evidenceError.value = error.response?.data?.detail || 'Failed to load evidence';
  } finally {
    loadingEvidence.value = false;
  }
};

const handleDownloadEvidence = async (evidenceItem) => {
  try {
    const blob = await evidenceService.downloadEvidence(evidenceItem.id);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = evidenceItem.title;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (error) {
    console.error('Failed to download evidence:', error);
  }
};

const handleDeleteEvidence = async (evidenceItem) => {
  if (!confirm('Are you sure you want to delete this evidence?')) return;

  try {
    await evidenceService.deleteEvidence(evidenceItem.id);
    evidence.value = evidence.value.filter((e) => e.id !== evidenceItem.id);
  } catch (error) {
    console.error('Failed to delete evidence:', error);
  }
};

const handleEvidenceUpload = async (newEvidenceList) => {
  evidence.value = [...evidence.value, ...newEvidenceList];
};

const handleEvidenceMoved = (updatedEvidenceList, openState) => {
  // Update the evidence list with optimistic changes
  evidence.value = updatedEvidenceList;

  // Restore the folder open state if provided
  if (openState && evidenceListRef.value) {
    evidenceListRef.value.restoreOpenState(openState);
  }
};


const handleUploadToFolder = (folder) => {
  uploadTargetFolder.value = folder;
  showUploadEvidenceModal.value = true;
};

const handleExtractMetadata = async (evidenceItem) => {
  selectedEvidenceForMetadata.value = evidenceItem;
  extractedMetadata.value = null;
  metadataError.value = '';
  loadingMetadata.value = true;
  showMetadataModal.value = true;

  try {
    const metadata = await evidenceService.extractMetadata(evidenceItem.id);
    extractedMetadata.value = metadata;
  } catch (error) {
    metadataError.value = error.response?.data?.detail || error.message || 'Failed to extract metadata';
  } finally {
    loadingMetadata.value = false;
  }
};

const handleViewTextContent = async (evidenceItem) => {
  selectedEvidenceForTextContent.value = evidenceItem;
  textContent.value = '';
  textFileInfo.value = null;
  textContentError.value = '';
  loadingTextContent.value = true;
  showTextContentModal.value = true;

  try {
    const response = await evidenceService.getEvidenceContent(evidenceItem.id);
    if (response.success) {
      textContent.value = response.content;
      textFileInfo.value = response.file_info;
    } else {
      textContentError.value = response.error || 'Failed to load file content';
    }
  } catch (error) {
    textContentError.value = error.response?.data?.detail || error.message || 'Failed to load file content';
  } finally {
    loadingTextContent.value = false;
  }
};

const handleViewImageContent = async (evidenceItem) => {
  selectedEvidenceForImageContent.value = evidenceItem;
  imageFileInfo.value = null;
  imageContentError.value = '';
  loadingImageContent.value = false; // Set to false since ImageContentModal handles its own loading
  showImageContentModal.value = true;

  // Set basic file info that we have
  imageFileInfo.value = {
    filename: evidenceItem.title,
    file_size: evidenceItem.file_size || 0, // This might need to be added to the evidence model
  };
};

// Hunt-related methods
const loadCaseHuntExecutions = async () => {
  if (!route.params.id) return;

  try {
    loadingHuntExecutions.value = true;
    const executions = await huntStore.getCaseExecutions(Number(route.params.id));
    caseHuntExecutions.value = executions;
  } catch (error) {
    console.error('Failed to load hunt executions:', error);
    caseHuntExecutions.value = [];
  } finally {
    loadingHuntExecutions.value = false;
  }
};

const getHuntStatusColor = (status) => {
  switch (status) {
    case 'pending': return 'grey';
    case 'running': return 'primary';
    case 'completed': return 'success';
    case 'failed': return 'error';
    case 'cancelled': return 'warning';
    default: return 'grey';
  }
};

const getHuntStatusIcon = (status) => {
  switch (status) {
    case 'pending': return 'mdi-clock-outline';
    case 'running': return 'mdi-play';
    case 'completed': return 'mdi-check';
    case 'failed': return 'mdi-close';
    case 'cancelled': return 'mdi-stop';
    default: return 'mdi-help';
  }
};

const formatDateTime = (dateString) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  return date.toLocaleString();
};

const viewHuntExecution = (executionId) => {
  router.push(`/hunts/execution/${executionId}`);
};

const getEntityDisplayName = (entity) => {
  if (!entity) return '';
  if (entity.entity_type === 'person') {
    return `${entity.data.first_name} ${entity.data.last_name}`.trim();
  } else if (entity.entity_type === 'company') {
    return entity.data.name;
  } else if (entity.entity_type === 'domain') {
    return entity.data.domain;
  } else if (entity.entity_type === 'ip_address') {
    return entity.data.ip_address;
  } else if (entity.entity_type === 'vehicle') {
    return `${entity.data.make} ${entity.data.model}`.trim();
  }
  return 'Unknown Entity';
};

const getFormattedHuntTitle = (execution) => {
  const baseName = execution.hunt_display_name || 'Hunt Execution';
  const initialParams = execution.initial_parameters || {};
  const huntCategory = execution.hunt_category || 'general';

  return formatHuntExecutionTitle(baseName, initialParams, huntCategory);
};

onMounted(() => {
  loadCaseData();
  loadEvidence();
  loadCaseHuntExecutions();
});
</script>
