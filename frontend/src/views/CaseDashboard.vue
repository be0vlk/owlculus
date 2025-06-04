<template>
  <v-app>
    <Sidebar />
    
    <v-main>
      <v-container class="pa-6">
        <!-- Loading state -->
        <v-card-text v-if="loading" class="text-center pa-16">
          <v-progress-circular
            size="64"
            width="4"
            color="primary"
            indeterminate
          />
          <v-card-text class="text-h6 mt-4">Loading case...</v-card-text>
        </v-card-text>

        <!-- Error state -->
        <v-alert
          v-else-if="error"
          type="error"
          class="ma-4"
          :text="error"
          prominent
          border="start"
        />

        <!-- Case Content -->
        <div v-else-if="caseData">
          <!-- Page Header -->
          <div class="mb-6">
            <v-row align="center" justify="space-between">
              <v-col>
                <h1 class="text-h3 font-weight-bold">
                  {{ caseData?.case_number }}
                </h1>
              </v-col>
              <v-col cols="auto">
                <div class="d-flex ga-2">
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
                </div>
              </v-col>
            </v-row>
          </div>
          <!-- Case Details -->
          <v-card class="mb-6">
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <CaseDetail :case-data="caseData" :client="client" />
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <!-- Case Tabs -->
          <v-card>
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
                  <div class="mb-4">
                    <v-btn
                      color="primary"
                      prepend-icon="mdi-plus"
                      @click="showNewEntityModal = true"
                    >
                      Add Entity
                    </v-btn>
                  </div>

                  <!-- Entities Loading -->
                  <v-card-text v-if="loadingEntities" class="text-center pa-8">
                    <v-progress-circular
                      size="50"
                      width="4"
                      color="primary"
                      indeterminate
                    />
                  </v-card-text>

                  <!-- Entities Error -->
                  <v-alert
                    v-else-if="entityError"
                    type="error"
                    class="mb-4"
                    :text="entityError"
                  />

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
                        <v-card-text v-else class="text-center text-medium-emphasis">
                          No people entities found.
                        </v-card-text>
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
                        <v-card-text v-else class="text-center text-medium-emphasis">
                          No company entities found.
                        </v-card-text>
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
                        <v-card-text v-else class="text-center text-medium-emphasis">
                          No domains found.
                        </v-card-text>
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
                        <v-card-text v-else class="text-center text-medium-emphasis">
                          No IP addresses found.
                        </v-card-text>
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
                        <v-card-text v-else class="text-center text-medium-emphasis">
                          No network assets found.
                        </v-card-text>
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
                        <v-card-text v-else class="text-center text-medium-emphasis">
                          No network asset entities found.
                        </v-card-text>
                      </div>
                    </template>
                  </EntityTabs>
                </div>

                <!-- Evidence Tab -->
                <div v-else-if="activeTab === 'evidence'" class="pa-4">
                  <div class="mb-4">
                    <v-btn
                      color="primary"
                      prepend-icon="mdi-upload"
                      @click="showUploadEvidenceModal = true"
                    >
                      Upload Evidence
                    </v-btn>
                  </div>
                  <EvidenceList
                    :evidence-list="evidence"
                    :loading="loadingEvidence"
                    :error="evidenceError"
                    @download="handleDownloadEvidence"
                    @delete="handleDeleteEvidence"
                  />
                </div>

                <!-- Notes Tab -->
                <div v-else-if="activeTab === 'notes'" class="pa-4">
                  <NoteEditor
                    v-model="caseData.notes"
                    :case-id="Number(route.params.id)"
                    @update:modelValue="handleNotesUpdate"
                  />
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
      @close="showUploadEvidenceModal = false"
      @uploaded="handleEvidenceUpload"
    />
  </v-app>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
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
import { caseService } from '../services/case';
import { clientService } from '../services/client';
import { entityService } from '../services/entity';
import { evidenceService } from '../services/evidence';

const route = useRoute();
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
    evidence.value = await evidenceService.getEvidenceForCase(Number(route.params.id));
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

const formatNetworkAssetDetails = (data) => {
  const details = [];
  if (data.domains?.length > 1) details.push(`${data.domains.length} domains`);
  if (data.ip_addresses?.length) details.push(`${data.ip_addresses.length} IPs`);
  if (data.subdomains?.length) details.push(`${data.subdomains.length} subdomains`);
  return details.join(', ') || 'No details';
};

onMounted(() => {
  loadCaseData();
  loadEntities();
  loadEvidence();
});
</script>