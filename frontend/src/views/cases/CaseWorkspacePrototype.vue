<!--
THROWAWAY: Three structurally different case workspaces on /case/:id?variant=A|B|C.
Question: how should case identity, navigation, and investigative content share the page?
Option A selected, with one Runs workspace for plugins and hunts. Mutations remain in memory.
-->
<template>
  <Sidebar />
  <v-main class="case-workspace-prototype" :class="`prototype-${variant.toLowerCase()}`">
    <component :is="layouts[variant]">
      <template #identity>
        <div class="prototype-identity">
          <div class="identity-copy">
            <div class="identity-reference">
              <span>{{ localCase.case_number }}</span
              ><v-chip size="x-small" variant="tonal" color="success">{{
                localCase.status
              }}</v-chip>
            </div>
            <h1 :title="localCase.title">{{ localCase.title }}</h1>
          </div>
          <div class="identity-actions">
            <v-btn
              prepend-icon="mdi-download"
              variant="outlined"
              @click="notify('Case export preview — a case bundle would download here.')"
              >Export</v-btn
            >
            <v-btn
              prepend-icon="mdi-information-outline"
              variant="tonal"
              @click="detailsOpen = true"
              >Case details</v-btn
            >
          </div>
        </div>
      </template>
      <template #tabs>
        <v-tabs
          v-model="activeTab"
          :direction="variant === 'C' && width > 700 ? 'vertical' : 'horizontal'"
          :show-arrows="true"
          :color="isDark ? 'teal-lighten-3' : 'primary'"
          class="workspace-tabs"
          aria-label="Case workspaces"
        >
          <v-tab
            v-for="tab in tabs"
            :key="tab.name"
            :value="tab.name"
            :prepend-icon="variant === 'C' ? tab.icon : undefined"
            :text="tab.label"
          />
        </v-tabs>
      </template>
      <CaseWorkspacePrototypeContent
        :tab="activeTab"
        :case-id="localCase.id"
        :state="state"
        :entities="entities"
        :evidence="evidence"
        :runs="runs"
        :can-view-hunts="canViewHunts"
        @action="openAction"
        @inspect="inspectItem"
        @notify="notify"
        @remove="entities = entities.filter((item) => item.id !== $event)"
      />
    </component>

    <v-dialog
      v-model="detailsOpen"
      class="prototype-details-dialog"
      aria-label="Case details"
      :transition="false"
    >
      <v-card rounded="0" class="details-card">
        <v-card-title class="d-flex align-center pa-5"
          ><h2 class="panel-title">Case details</h2>
          <v-spacer /><v-btn
            icon="mdi-close"
            variant="text"
            aria-label="Close case details"
            @click="detailsOpen = false"
        /></v-card-title>
        <v-divider />
        <v-card-text class="pa-6">
          <div class="detail-reference">{{ localCase.case_number }}</div>
          <h3 class="mb-6">{{ localCase.title }}</h3>
          <dl class="case-metadata">
            <dt>Status</dt>
            <dd>
              <v-chip color="success" variant="tonal" size="small">{{ localCase.status }}</v-chip>
            </dd>
            <dt>Client</dt>
            <dd>{{ client?.name || 'No client assigned' }}</dd>
            <dt>Created</dt>
            <dd>
              {{
                new Date(localCase.created_at).toLocaleDateString('en-GB', {
                  day: 'numeric',
                  month: 'long',
                  year: 'numeric',
                })
              }}
            </dd>
          </dl>
          <div class="members-heading">
            <h3>Assigned users</h3>
            <v-btn variant="text" size="small" @click="openAction('Manage Users')"
              >Manage Users</v-btn
            >
          </div>
          <div v-for="user in localCase.users" :key="user.id" class="case-member">
            <v-avatar color="primary" variant="tonal" size="34">{{
              user.username
                .split(' ')
                .map((word) => word[0])
                .slice(0, 2)
                .join('')
            }}</v-avatar
            ><span>{{ user.username }}</span
            ><v-chip v-if="user.is_lead" size="x-small" variant="tonal">Lead</v-chip>
          </div>
          <p v-if="!localCase.users.length">No users assigned</p>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-5"
          ><v-btn
            prepend-icon="mdi-pencil-outline"
            variant="outlined"
            @click="openAction('Edit Case')"
            >Edit Case</v-btn
          ></v-card-actions
        >
      </v-card>
    </v-dialog>

    <v-dialog v-model="actionOpen" :aria-label="actionName" max-width="540">
      <v-card>
        <v-card-title class="pa-5">{{ actionName }}</v-card-title>
        <v-card-text>
          <p class="text-body-medium text-medium-emphasis mb-5">
            Try the placement and flow. Changes in this preview last until the page reloads.
          </p>
          <template v-if="actionName === 'Manage Users'">
            <v-checkbox
              v-for="user in localCase.users"
              :key="user.id"
              v-model="selectedMembers"
              :value="user.id"
              :label="user.username"
              hide-details
              density="compact"
            />
          </template>
          <template v-else>
            <v-text-field
              v-model="actionValue"
              :label="
                actionName === 'Edit Case'
                  ? 'Case title'
                  : actionName === 'Upload Evidence'
                    ? 'File name'
                    : actionName === 'Add Entity'
                      ? 'Domain name'
                      : 'Title'
              "
              autofocus
              hide-details
            />
            <v-select
              v-if="actionName === 'Edit Case'"
              v-model="editStatus"
              label="Status"
              :items="['Open', 'Closed']"
              class="mt-4"
              hide-details
            />
          </template>
        </v-card-text>
        <v-card-actions class="pa-5"
          ><v-spacer /><v-btn variant="text" @click="actionOpen = false">Cancel</v-btn
          ><v-btn
            color="primary"
            :disabled="actionName !== 'Manage Users' && !actionValue.trim()"
            @click="applyAction"
            >{{
              actionName === 'Add Entity'
                ? 'Add Entity'
                : actionName === 'Upload Evidence'
                  ? 'Upload Evidence'
                  : 'Save'
            }}</v-btn
          ></v-card-actions
        >
      </v-card>
    </v-dialog>

    <v-dialog
      :model-value="!!selectedItem"
      max-width="680"
      aria-label="Selected record"
      @update:model-value="selectedItem = null"
    >
      <v-card v-if="selectedItem">
        <v-card-title class="d-flex align-center pa-5"
          ><span class="text-wrap">{{
            selectedItem.title || selectedItem.display_name || entityName(selectedItem)
          }}</span
          ><v-spacer /><v-btn
            icon="mdi-close"
            variant="text"
            aria-label="Close record"
            @click="selectedItem = null"
        /></v-card-title>
        <v-divider />
        <v-card-text class="pa-6">
          <template v-if="selectedItem.entity_type"
            ><p class="detail-reference mb-3">{{ selectedItem.entity_type.replace('_', ' ') }}</p>
            <dl class="record-fields">
              <template v-for="(value, key) in selectedItem.data" :key="key"
                ><dt>{{ key.replaceAll('_', ' ') }}</dt>
                <dd>{{ Array.isArray(value) ? value.join(', ') : value }}</dd></template
              >
            </dl></template
          >
          <template v-else-if="selectedItem.run_type"
            ><v-chip
              :color="selectedItem.status === 'failed' ? 'error' : 'success'"
              variant="tonal"
              class="mb-4"
              >{{ selectedItem.status }}</v-chip
            >
            <p>
              {{
                selectedItem.error?.message ||
                'Retained result preview. This sample run has already completed.'
              }}
            </p>
            <pre class="run-result">{{
              JSON.stringify(
                {
                  input: selectedItem.parameters,
                  records:
                    selectedItem.run_type === 'Hunt'
                      ? selectedItem.steps
                      : selectedItem.status === 'completed'
                        ? [
                            { type: 'A', value: '203.0.113.24' },
                            { type: 'MX', value: 'mail.northstar.example' },
                          ]
                        : [],
                },
                null,
                2,
              )
            }}</pre>
            <v-btn
              prepend-icon="mdi-download"
              variant="outlined"
              @click="notify('Retained result export preview')"
              >Export results</v-btn
            ></template
          >
          <template v-else
            ><p>{{ selectedItem.description }}</p>
            <div class="file-preview">
              <v-icon size="52" color="primary">mdi-file-document-outline</v-icon>
              <p class="mt-3">{{ selectedItem.title }}</p>
              <span class="text-body-small text-medium-emphasis"
                >Sample file · preview placement only</span
              >
            </div>
            <v-btn
              prepend-icon="mdi-download"
              variant="outlined"
              @click="notify('Evidence download preview')"
              >Download</v-btn
            ></template
          >
        </v-card-text>
      </v-card>
    </v-dialog>
    <v-snackbar v-model="snackbar" :timeout="3500" location="top center" role="status"
      >{{ message
      }}<template #actions
        ><v-btn variant="text" @click="snackbar = false">Dismiss</v-btn></template
      ></v-snackbar
    >
  </v-main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { useDarkMode } from '@/composables/useDarkMode'
import { useDialogFocusRestore } from '@/composables/useDialogFocusRestore'
import { useAuthStore } from '@/stores/auth'
import { entityService } from '@/services/entity'
import { pluginService } from '@/services/plugin'
import { huntService } from '@/services/hunt'
import Sidebar from '@/components/Sidebar.vue'
import VariantA from './CaseWorkspacePrototypeVariantA.vue'
import VariantB from './CaseWorkspacePrototypeVariantB.vue'
import VariantC from './CaseWorkspacePrototypeVariantC.vue'
import CaseWorkspacePrototypeContent from './CaseWorkspacePrototypeContent.vue'

const props = defineProps({
  caseData: { type: Object, required: true },
  client: { type: Object, default: null },
  evidence: { type: Array, default: () => [] },
  huntExecutions: { type: Array, default: () => [] },
})
const emit = defineEmits(['state'])
const route = useRoute()
const router = useRouter()
const { width } = useDisplay()
const { isDark } = useDarkMode()
const auth = useAuthStore()
const canViewHunts = computed(() => auth.user?.role !== 'Analyst')
const layouts = { A: VariantA, B: VariantB, C: VariantC }
const variant = computed(() =>
  ['A', 'B', 'C'].includes(route.query.variant) ? route.query.variant : 'A',
)
const tabs = computed(() => [
  { name: 'entities', label: 'Entities', icon: 'mdi-account-group-outline' },
  { name: 'evidence', label: 'Evidence', icon: 'mdi-folder-outline' },
  { name: 'tasks', label: 'Tasks', icon: 'mdi-checkbox-marked-circle-outline' },
  { name: 'runs', label: 'Runs', icon: 'mdi-history' },
  { name: 'notes', label: 'Notes', icon: 'mdi-note-text-outline' },
])
const activeTab = computed({
  get: () => {
    if (route.query.tab === 'plugin-runs' || (route.query.tab === 'hunts' && canViewHunts.value))
      return 'runs'
    return tabs.value.some((tab) => tab.name === route.query.tab) ? route.query.tab : 'entities'
  },
  set: (tab) => {
    const query = { ...route.query }
    if (tab === 'entities') delete query.tab
    else query.tab = tab
    router.replace({ query })
  },
})
const localCase = reactive({
  ...props.caseData,
  users: props.caseData.users.map((user) => ({ ...user })),
})
const entities = ref([])
const pluginRuns = ref([])
const runs = computed(() =>
  [
    ...pluginRuns.value.map((run) => ({
      ...run,
      key: `plugin:${run.id}`,
      run_type: 'Plugin',
      display_name: run.plugin_name,
    })),
    ...(canViewHunts.value
      ? props.huntExecutions.map((run) => ({
          ...run,
          key: `hunt:${run.id}`,
          run_type: 'Hunt',
          display_name: run.hunt_display_name,
          parameters: run.initial_parameters,
        }))
      : []),
  ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
)
const detailsOpen = ref(false)
const actionOpen = ref(false)
useDialogFocusRestore(detailsOpen)
useDialogFocusRestore(actionOpen)
const actionName = ref('')
const actionValue = ref('')
const editStatus = ref('Open')
const selectedMembers = ref([])
const selectedItem = ref(null)
async function inspectItem(item) {
  selectedItem.value = item
  if (item.run_type === 'Hunt') {
    const details = await huntService.getExecution(item.id, true)
    if (selectedItem.value?.key === item.key) selectedItem.value = { ...item, steps: details.steps }
  }
}
const snackbar = ref(false)
const message = ref('')
const state = reactive({
  search: '',
  entityTypes: [],
  selected: [],
  folder: null,
  evidenceSearch: '',
  notes: props.caseData.notes || '',
  savedNotes: props.caseData.notes || '',
  editingNotes: false,
  addedEvidence: [],
  tasks: [
    {
      id: 1,
      title: 'Cross-check registry addresses against archived contact pages',
      owner: 'Alex Morgan',
      done: false,
    },
    {
      id: 2,
      title: 'Review historical DNS records and retain source links',
      owner: 'Sam Rivera',
      done: false,
    },
    {
      id: 3,
      title: 'Collect the current company registry extract',
      owner: 'Jamie Chen',
      done: true,
    },
  ],
})
function entityName(item) {
  const data = item.data || {}
  return (
    data.domain ||
    data.name ||
    data.ip_address ||
    [data.first_name, data.last_name].filter(Boolean).join(' ') ||
    [data.make, data.model].join(' ')
  )
}
function notify(text) {
  message.value = text
  snackbar.value = true
}
function openAction(name) {
  actionName.value = name
  actionValue.value = name === 'Edit Case' ? localCase.title : ''
  editStatus.value = localCase.status
  selectedMembers.value = localCase.users.map((user) => user.id)
  actionOpen.value = true
}
function applyAction() {
  if (actionName.value === 'Edit Case') {
    localCase.title = actionValue.value
    localCase.status = editStatus.value
  } else if (actionName.value === 'Manage Users')
    localCase.users = localCase.users.filter((user) => selectedMembers.value.includes(user.id))
  else if (actionName.value === 'Add Entity')
    entities.value.unshift({
      id: Date.now(),
      entity_type: 'domain',
      data: { domain: actionValue.value, description: 'Added in this preview' },
      created_at: '2026-09-07T09:00:00Z',
    })
  else if (actionName.value === 'Upload Evidence')
    state.addedEvidence.push({
      id: Date.now(),
      title: actionValue.value,
      parent_folder_id: state.folder || 101,
      file_size: 12000,
      description: 'Added in this preview',
    })
  else if (actionName.value === 'Add Task')
    state.tasks.push({
      id: Date.now(),
      title: actionValue.value,
      owner: 'Alex Morgan',
      done: false,
    })
  actionOpen.value = false
  notify(`${actionName.value}: preview updated in memory`)
}
onMounted(async () => {
  const [caseEntities, history] = await Promise.all([
    entityService.getCaseEntities(props.caseData.id),
    pluginService.getHistory(props.caseData.id),
  ])
  entities.value = caseEntities
  pluginRuns.value = history.items
})
watch(
  () => ({
    variant: variant.value,
    tab: activeTab.value,
    caseId: localCase.id,
    caseTitle: localCase.title,
    status: localCase.status,
    detailsOpen: detailsOpen.value,
    theme: isDark.value ? 'dark' : 'light',
    ...state,
    entityCount: entities.value.length,
    visibleRuns: runs.value.map((run) => ({
      key: run.key,
      type: run.run_type,
      name: run.display_name,
      status: run.status,
    })),
  }),
  (snapshot) => {
    emit('state', snapshot)
    console.info('[Case workspace prototype state]', JSON.parse(JSON.stringify(snapshot)))
  },
  { deep: true, immediate: true },
)
</script>

<style scoped>
.case-workspace-prototype {
  color: rgb(var(--v-theme-on-surface));
}

.prototype-identity {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.identity-copy {
  min-width: 0;
}

.identity-reference {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
}

.identity-reference > span:first-child,
.detail-reference {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
  opacity: 0.7;
}

.prototype-identity h1 {
  margin: 0;
  font-size: 21px;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: -0.3px;
  overflow-wrap: anywhere;
}

.identity-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.identity-actions :deep(.v-btn) {
  font-size: 13px;
  letter-spacing: 0;
  height: 36px;
}

.workspace-tabs :deep(.v-tab) {
  font-size: 13px;
  letter-spacing: 0;
  text-transform: none;
  min-width: 85px;
}

.workspace-tabs :deep(.v-slide-group__prev),
.workspace-tabs :deep(.v-slide-group__next) {
  flex-basis: 30px;
  min-width: 30px;
}

.prototype-b .prototype-identity h1 {
  font-size: 24px;
}

.prototype-b .identity-reference {
  margin-bottom: 8px;
}

.prototype-c .workspace-tabs :deep(.v-tab) {
  justify-content: flex-start;
  border-radius: 6px;
  margin-bottom: 5px;
  padding-inline: 12px;
}

.prototype-c .workspace-tabs :deep(.v-tab--selected) {
  background: rgb(var(--v-theme-primary), 0.1);
}

.prototype-c .workspace-tabs :deep(.v-tab__slider) {
  display: none;
}

.panel-title {
  font-size: 18px;
  font-weight: 600;
}

.prototype-details-dialog :deep(.v-overlay__content) {
  position: fixed;
  right: 0;
  top: 0;
  width: 420px;
  max-width: 100%;
  height: 100%;
  max-height: 100%;
  margin: 0;
}

.details-card {
  height: 100%;
}

.case-metadata dt,
.record-fields dt {
  font-size: 12px;
  opacity: 0.65;
  margin-bottom: 4px;
}

.case-metadata dd,
.record-fields dd {
  margin-bottom: 24px;
  font-size: 14px;
  overflow-wrap: anywhere;
}

.members-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 32px 0 16px;
}

.members-heading h3 {
  font-size: 14px;
}

.case-member {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 13px;
}

.case-member .v-avatar {
  font-size: 11px;
}

.file-preview {
  text-align: center;
  padding: 44px 20px;
  margin: 20px 0;
  border: 1px dashed rgb(var(--v-border-color), 0.3);
  border-radius: 8px;
}

.run-result {
  margin: 20px 0;
  padding: 20px;
  background: rgb(var(--v-theme-on-surface), 0.05);
  overflow: auto;
  font-size: 12px;
}

@media (width <= 1100px) {
  .prototype-identity {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
  }
}

@media (width <= 600px) {
  .prototype-identity h1,
  .prototype-b .prototype-identity h1 {
    font-size: 18px;
  }

  .identity-actions {
    flex-wrap: wrap;
  }

  .identity-actions :deep(.v-btn) {
    font-size: 12px;
  }
}
</style>
