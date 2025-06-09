<template>
  <v-app>
    <Sidebar />
    
    <v-main>
      <v-container fluid class="pa-6">
        <!-- Loading state -->
        <v-row v-if="loading" justify="center" align="center" class="fill-height">
          <v-col cols="12" class="text-center">
            <v-card variant="outlined" class="pa-8 mx-auto" max-width="400">
              <v-progress-circular
                size="64"
                width="4"
                color="primary"
                indeterminate
                class="mb-4"
              />
              <div class="text-h6">Loading case...</div>
              <div class="text-body-2 text-medium-emphasis">Please wait while we load your case data</div>
            </v-card>
          </v-col>
        </v-row>

        <!-- Error state -->
        <v-row v-else-if="error" justify="center">
          <v-col cols="12" md="8" lg="6">
            <v-alert
              type="error"
              variant="tonal"
              border="start"
              prominent
              icon="mdi-alert-circle"
              class="ma-4"
            >
              <v-alert-title>Error Loading Case</v-alert-title>
              {{ error }}
            </v-alert>
          </v-col>
        </v-row>

        <!-- Case Content -->
        <div v-else-if="caseData">
          <!-- Page Header Card -->
          <v-card class="mb-6" variant="outlined">
            <v-card-title class="d-flex align-center pa-6">
              <v-icon start size="large" color="primary">mdi-briefcase</v-icon>
              <div class="text-h4 font-weight-bold">
                {{ caseData?.case_number }}
              </div>
              <v-spacer />
              <v-btn-group variant="outlined" divided>
                <v-btn
                  color="primary"
                  prepend-icon="mdi-pencil"
                  @click="showEditModal = true"
                >
                  Edit Case
                </v-btn>
                <v-btn
                  color="primary"
                  prepend-icon="mdi-account-plus"
                  @click="showAddUserModal = true"
                >
                  Add User
                </v-btn>
              </v-btn-group>
            </v-card-title>
          </v-card>
          <!-- Case Details -->
          <v-card class="mb-6" variant="outlined">
            <v-card-title class="d-flex align-center">
              <v-icon start>mdi-information</v-icon>
              Case Information
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

          <!-- Case Tabs -->
          <v-card variant="outlined">
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

                  <!-- Entities Loading -->
                  <v-row v-if="loadingEntities" justify="center">
                    <v-col cols="12" class="text-center">
                      <v-card variant="outlined" class="pa-8">
                        <v-progress-circular
                          size="64"
                          width="4"
                          color="primary"
                          indeterminate
                          class="mb-4"
                        />
                        <div class="text-h6">Loading entities...</div>
                      </v-card>
                    </v-col>
                  </v-row>

                  <!-- Entities Error -->
                  <v-alert
                    v-else-if="entityError"
                    type="error"
                    variant="tonal"
                    border="start"
                    icon="mdi-alert-circle"
                    class="mb-6"
                  >
                    <v-alert-title>Error Loading Entities</v-alert-title>
                    {{ entityError }}
                  </v-alert>

                  <!-- Entity Types Tabs -->
                  <EntityTabs v-else :entity-types="Object.keys(groupedEntities)">
                    <template #default="{ activeType }">
                      <!-- Person Entities -->
                      <div v-if="activeType === 'person'">
                        <div v-if="groupedEntities.person?.length">
                          <EntityListItem
                            v-for="entity in groupedEntities.person"
                            :key="entity.id"
                            @viewDetails="showEntityDetails(entity)"
                          >
                            <template #name>
                              {{ entity.data.first_name }} {{ entity.data.last_name }}
                            </template>
                            <template #detail>
                              {{ entity.data.email }}
                            </template>
                          </EntityListItem>
                        </div>
                        <v-empty-state
                          v-else
                          icon="mdi-account-outline"
                          title="No People Found"
                          text="No person entities have been added to this case yet."
                        />
                      </div>

                      <!-- Company Entities -->
                      <div v-if="activeType === 'company'">
                        <div v-if="groupedEntities.company?.length">
                          <EntityListItem
                            v-for="entity in groupedEntities.company"
                            :key="entity.id"
                            @viewDetails="showEntityDetails(entity)"
                          >
                            <template #name>
                              {{ entity.data.name }}
                            </template>
                            <template #detail>
                              {{ entity.data.website }}
                            </template>
                          </EntityListItem>
                        </div>
                        <v-empty-state
                          v-else
                          icon="mdi-domain"
                          title="No Companies Found"
                          text="No company entities have been added to this case yet."
                        />
                      </div>

                      <!-- Domain Entities -->
                      <div v-if="activeType === 'domain'">
                        <div v-if="groupedEntities.domain?.length">
                          <EntityListItem
                            v-for="entity in groupedEntities.domain"
                            :key="entity.id"
                            @viewDetails="showEntityDetails(entity)"
                          >
                            <template #name>
                              {{ entity.data.domain }}
                            </template>
                            <template #detail>
                              {{ entity.data.description || 'No description' }}
                            </template>
                          </EntityListItem>
                        </div>
                        <v-empty-state
                          v-else
                          icon="mdi-web"
                          title="No Domains Found"
                          text="No domain entities have been added to this case yet."
                        />
                      </div>

                      <!-- IP Address Entities -->
                      <div v-if="activeType === 'ip_address'">
                        <div v-if="groupedEntities.ip_address?.length">
                          <EntityListItem
                            v-for="entity in groupedEntities.ip_address"
                            :key="entity.id"
                            @viewDetails="showEntityDetails(entity)"
                          >
                            <template #name>
                              {{ entity.data.ip_address }}
                            </template>
                            <template #detail>
                              {{ entity.data.description || 'No description' }}
                            </template>
                          </EntityListItem>
                        </div>
                        <v-empty-state
                          v-else
                          icon="mdi-ip"
                          title="No IP Addresses Found"
                          text="No IP address entities have been added to this case yet."
                        />
                      </div>

                      <!-- Network Assets Entities -->
                      <div v-if="activeType === 'network_assets'">
                        <div v-if="groupedEntities.network_assets?.length">
                          <EntityListItem
                            v-for="entity in groupedEntities.network_assets"
                            :key="entity.id"
                            @viewDetails="showEntityDetails(entity)"
                          >
                            <template #name>
                              {{ entity.data.domains?.length ? entity.data.domains[0] : 'Unnamed Network Asset' }}
                            </template>
                            <template #detail>
                              {{ formatNetworkAssetDetails(entity.data) }}
                            </template>
                          </EntityListItem>
                        </div>
                        <v-empty-state
                          v-else
                          icon="mdi-server-network"
                          title="No Network Assets Found"
                          text="No network asset entities have been added to this case yet."
                        />
                      </div>

                      <!-- Network Entities -->
                      <div v-if="activeType === 'network'">
                        <div v-if="groupedEntities.network?.length">
                          <EntityListItem
                            v-for="entity in groupedEntities.network"
                            :key="entity.id"
                            :has-detail="hasNetworkAssetDetails(entity)"
                            @viewDetails="showEntityDetails(entity)"
                          >
                            <template #name>
                              Network Asset
                            </template>
                            <template #detail>
                              <div v-if="entity.data.domains?.length" class="mb-1">
                                <strong>Domains:</strong> {{ entity.data.domains.join(', ') }}
                              </div>
                              <div v-if="entity.data.ip_addresses?.length" class="mb-1">
                                <strong>IPs:</strong> {{ entity.data.ip_addresses.join(', ') }}
                              </div>
                              <div v-if="entity.data.email_addresses?.length">
                                <strong>Emails:</strong> {{ entity.data.email_addresses.join(', ') }}
                              </div>
                            </template>
                          </EntityListItem>
                        </div>
                        <v-empty-state
                          v-else
                          icon="mdi-server-network"
                          title="No Network Entities Found"
                          text="No network entities have been added to this case yet."
                        />
                      </div>
                    </template>
                  </EntityTabs>
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
      </v-container>
    </v-main>

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
  </v-app>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import Sidebar from '../components/Sidebar.vue';
import CaseDetail from '../components/CaseDetail.vue';
import EntityListItem from '../components/EntityListItem.vue';
import EntityTabs from '../components/EntityTabs.vue';
import CaseTabs from '../components/CaseTabs.vue';
import EditCaseModal from '../components/EditCaseModal.vue';
import AddUserToCaseModal from '../components/AddUserToCaseModal.vue';
import NewEntityModal from '../components/NewEntityModal.vue';
import EntityDetailsModal from '../components/EntityDetailsModal.vue';
import NoteEditor from '../components/NoteEditor.vue';
import EvidenceList from '../components/EvidenceList.vue';
import UploadEvidenceModal from '../components/UploadEvidenceModal.vue';
import MetadataModal from '../components/MetadataModal.vue';
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
    
    // Reload all entities to get updated relationships
    await loadEntities();
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

const loadEntities = async () => {
  try {
    loadingEntities.value = true;
    entityError.value = null;
    const caseId = route.params.id;
    const response = await entityService.getCaseEntities(caseId);
    entities.value = response;
  } catch (err) {
    entityError.value = err.message || 'Failed to load entities';
    console.error('Error loading entities:', err);
  } finally {
    loadingEntities.value = false;
  }
};

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
  loadEntities();
  loadEvidence();
});
</script>