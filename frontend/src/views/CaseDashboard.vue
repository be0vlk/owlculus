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
              :tabs="[
                { name: 'entities', label: 'Entities' },
                { name: 'evidence', label: 'Evidence' },
                { name: 'notes', label: 'Notes' },
              ]"
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
                  />
                </div>

                <!-- Notes Tab -->
                <div v-else-if="activeTab === 'notes'" class="pa-6">
                  <v-card variant="outlined">
                    <v-card-title class="d-flex align-center">
                      <v-icon start>mdi-note-text</v-icon>
                      Case Notes
                    </v-card-title>
                    <v-divider />
                    <v-card-text class="pa-0">
                      <NoteEditor
                        v-model="caseData.notes"
                        :case-id="Number(route.params.id)"
                        @update:modelValue="handleNotesUpdate"
                      />
                    </v-card-text>
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
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from '../stores/auth';
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
import { caseService } from '../services/case';
import { clientService } from '../services/client';
import { entityService } from '../services/entity';
import { evidenceService } from '../services/evidence';

const route = useRoute();
const authStore = useAuthStore();
const loading = ref(false);
const loadingEntities = ref(false);
const error = ref(null);
const entityError = ref(null);
const caseData = ref(null);
const client = ref(null);
const entities = ref([]);
const entityTableRef = ref(null);
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
// Metadata extraction
const showMetadataModal = ref(false);
const selectedEvidenceForMetadata = ref(null);
const extractedMetadata = ref(null);
const loadingMetadata = ref(false);
const metadataError = ref('');

// Text content viewing
const showTextContentModal = ref(false);
const selectedEvidenceForTextContent = ref(null);
const textContent = ref('');
const textFileInfo = ref(null);
const loadingTextContent = ref(false);
const textContentError = ref('');

// Make entityService available to the template
const entityServiceRef = entityService;

// Computed properties
const userRole = computed(() => authStore.user?.role || 'Analyst');

const hasFolders = computed(() => {
  return evidence.value.some(item => item.is_folder);
});

// Entity details handling
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

    // Add any newly created associate entities
    if (createdAssociates.length > 0) {
      entities.value = [...entities.value, ...createdAssociates];
    }

    // Refresh the entity table to show updated entity and any new associates
    if (entityTableRef.value) {
      entityTableRef.value.refresh();
    }
  }
}

// Handle case update
const handleCaseUpdate = (updatedCase) => {
  Object.assign(caseData.value, updatedCase);
};

// Handle notes update
const handleNotesUpdate = (notes) => {
  if (caseData.value) {
    caseData.value.notes = notes;
  }
};

// Handle new entity creation
const handleNewEntity = (newEntity) => {
  entities.value = [...entities.value, newEntity];
  showEntityCreationSuccess.value = true;
  createdEntity.value = newEntity;
  
  // Refresh the entity table to show the new entity
  if (entityTableRef.value) {
    entityTableRef.value.refresh();
  }
};

// Handle entity creation success dialog actions
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

const handleEntityDeleted = (deletedEntities) => {
  // This will be handled by the EntityDataTable refresh
  console.log('Entities deleted:', deletedEntities);
};

// Computed property to group entities by type
const groupedEntities = computed(() => {
  return entities.value.reduce((groups, entity) => {
    const type = entity.entity_type;
    if (!groups[type]) {
      groups[type] = [];
    }
    groups[type].push(entity);
    return groups;
  }, {});
});

// Computed property to check if a network asset has details
const hasNetworkAssetDetails = (entity) => {
  return (
    entity.data.domains?.length ||
    entity.data.ip_addresses?.length ||
    entity.data.email_addresses?.length
  );
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

const formatNetworkAssetDetails = (data) => {
  const details = [];
  if (data.domains?.length > 1) details.push(`${data.domains.length} domains`);
  if (data.ip_addresses?.length) details.push(`${data.ip_addresses.length} IPs`);
  if (data.subdomains?.length) details.push(`${data.subdomains.length} subdomains`);
  return details.join(', ') || 'No details';
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
  }
  return 'Unknown Entity';
};

onMounted(() => {
  loadCaseData();
  loadEvidence();
});
</script>
