<template>
  <div class="min-h-screen bg-gray-100 dark:bg-gray-900">
    <div class="flex">
      <Sidebar class="fixed inset-y-0 left-0" />

      <div class="flex-1 ml-64">
        <header class="bg-white shadow dark:bg-gray-800">
          <div class="max-w-7xl mx-auto px-8 py-6">
            <div class="flex items-center justify-between">
              <h1 class="text-3xl font-bold text-gray-900 dark:text-white">
                {{ caseData?.case_number }}
              </h1>
              <div class="flex items-center space-x-4">
                <button
                  @click="showEditModal = true"
                  class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500"
                >
                  Edit Case
                </button>
                <button
                  @click="showAddUserModal = true"
                  class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500"
                >
                  Add User
                </button>
              </div>
            </div>
          </div>
        </header>

        <main class="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
          <LoadingSpinner v-if="loading" size="large" />
          <ErrorMessage v-else-if="error" :message="error" />

          <div v-else-if="caseData" class="bg-white dark:bg-gray-800 shadow rounded-lg">
            <div class="px-4 py-5 sm:p-6">
              <div class="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <CaseDetail :case-data="caseData" :client="client" class="dark:text-gray-200" />
              </div>
            </div>

            <div class="px-4 py-5 sm:p-6">
              <CaseTabs
                :tabs="[
                  { name: 'entities', label: 'Entities' },
                  { name: 'evidence', label: 'Evidence' },
                  { name: 'notes', label: 'Notes' },
                ]"
              >
                <template #default="{ activeTab }">
                  <div v-if="activeTab === 'entities'">
                    <div class="mb-4">
                      <button
                        @click="showNewEntityModal = true"
                        class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500"
                      >
                        Add Entity
                      </button>
                    </div>
                    <LoadingSpinner v-if="loadingEntities" size="medium" />
                    <ErrorMessage
                      v-else-if="entityError"
                      :message="entityError"
                    />
                    <EntityTabs v-else :entity-types="Object.keys(groupedEntities)">
                      <template #default="{ activeType }">
                        <ul
                          v-if="
                            activeType === 'person' &&
                            groupedEntities.person?.length
                          "
                          role="list"
                          class="divide-y divide-gray-200 dark:divide-gray-700"
                        >
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
                        </ul>
                        <div
                          v-if="
                            activeType === 'person' &&
                            !groupedEntities.person?.length
                          "
                          class="text-gray-500 dark:text-gray-400 p-4"
                        >
                          No people entities found.
                        </div>

                        <ul
                          v-if="
                            activeType === 'company' &&
                            groupedEntities.company?.length
                          "
                          role="list"
                          class="divide-y divide-gray-200 dark:divide-gray-700"
                        >
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
                        </ul>
                        <div
                          v-if="
                            activeType === 'company' &&
                            !groupedEntities.company?.length
                          "
                          class="text-gray-500 dark:text-gray-400 p-4"
                        >
                          No company entities found.
                        </div>

                        <ul
                          v-if="
                            activeType === 'domain' &&
                            groupedEntities.domain?.length
                          "
                          role="list"
                          class="divide-y divide-gray-200 dark:divide-gray-700"
                        >
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
                        </ul>
                        <div
                          v-if="
                            activeType === 'domain' &&
                            !groupedEntities.domain?.length
                          "
                          class="text-gray-500 dark:text-gray-400 p-4"
                        >
                          No domains found.
                        </div>

                        <ul
                          v-if="
                            activeType === 'ip_address' &&
                            groupedEntities.ip_address?.length
                          "
                          role="list"
                          class="divide-y divide-gray-200 dark:divide-gray-700"
                        >
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
                        </ul>
                        <div
                          v-if="
                            activeType === 'ip_address' &&
                            !groupedEntities.ip_address?.length
                          "
                          class="text-gray-500 dark:text-gray-400 p-4"
                        >
                          No IP addresses found.
                        </div>

                        <ul
                          v-if="
                            activeType === 'network_assets' &&
                            groupedEntities.network_assets?.length
                          "
                          role="list"
                          class="divide-y divide-gray-200 dark:divide-gray-700"
                        >
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
                        </ul>
                        <div
                          v-if="
                            activeType === 'network_assets' &&
                            !groupedEntities.network_assets?.length
                          "
                          class="text-gray-500 dark:text-gray-400 p-4"
                        >
                          No network assets found.
                        </div>

                        <ul
                          v-if="
                            activeType === 'network' &&
                            groupedEntities.network?.length
                          "
                          role="list"
                          class="divide-y divide-gray-200 dark:divide-gray-700"
                        >
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
                              <div v-if="entity.data.domains?.length">
                                Domains: {{ entity.data.domains.join(', ') }}
                              </div>
                              <div v-if="entity.data.ip_addresses?.length">
                                IPs: {{ entity.data.ip_addresses.join(', ') }}
                              </div>
                              <div v-if="entity.data.email_addresses?.length">
                                Emails:
                                {{ entity.data.email_addresses.join(', ') }}
                              </div>
                            </template>
                          </EntityListItem>
                        </ul>
                        <div
                          v-if="
                            activeType === 'network' &&
                            !groupedEntities.network?.length
                          "
                          class="text-gray-500 dark:text-gray-400 p-4"
                        >
                          No network asset entities found.
                        </div>
                      </template>
                    </EntityTabs>
                  </div>
                  <div v-else-if="activeTab === 'evidence'">
                    <div class="mb-4">
                      <button
                        @click="showUploadEvidenceModal = true"
                        class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500"
                      >
                        Upload Evidence
                      </button>
                    </div>
                    <EvidenceList
                      :evidence-list="evidence"
                      :loading="loadingEvidence"
                      :error="evidenceError"
                      @download="handleDownloadEvidence"
                      @delete="handleDeleteEvidence"
                    />
                  </div>
                  <div v-else-if="activeTab === 'notes'">
                    <NoteEditor
                      v-model="caseData.notes"
                      :case-id="Number(route.params.id)"
                      @update:modelValue="handleNotesUpdate"
                    />
                  </div>
                </template>
              </CaseTabs>
            </div>
          </div>
        </main>
      </div>
    </div>

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
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import Sidebar from '../components/Sidebar.vue';
import LoadingSpinner from '../components/LoadingSpinner.vue';
import ErrorMessage from '../components/ErrorMessage.vue';
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