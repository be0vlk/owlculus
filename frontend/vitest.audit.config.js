import { readFileSync } from 'node:fs'
import { defineConfig, mergeConfig } from 'vitest/config'
import vitestConfig from './vitest.config'

// Keep the collection and enforcement scopes identical, including unimported modules.
export const auditedTests = [
  'src/router/__tests__/roles.test.js',
  'src/services/__tests__/session.integration.test.js',
  'src/views/__tests__/Register.test.js',
  'src/components/__tests__/TaskDetailWorkflow.test.js',
  'src/components/__tests__/TaskTableWorkflow.test.js',
  'src/stores/__tests__/taskBulkWorkflow.test.js',
  'src/components/__tests__/EvidenceTemplateManagementCard.integration.test.js',
  'src/views/__tests__/EvidenceTemplates.integration.test.js',
]

export const auditedSources = [
  'src/App.vue',
  'src/router/index.js',
  'src/services/api.js',
  'src/services/auth.js',
  'src/stores/auth.js',
  'src/stores/activeCase.js',
  'src/views/Register.vue',
  'src/services/invite.js',
  'src/views/tasks/TaskDetail.vue',
  'src/views/cases/CaseTasks.vue',
  'src/components/tasks/TaskTable.vue',
  'src/components/tasks/TaskForm.vue',
  'src/components/tasks/TaskQuickEditDialog.vue',
  'src/components/tasks/TaskAssignDialog.vue',
  'src/components/tasks/CustomFieldInput.vue',
  'src/composables/useTaskTable.js',
  'src/stores/taskStore.js',
  'src/services/task.js',
  'src/components/EvidenceTemplateManagementCard.vue',
  'src/components/FolderEditor.vue',
  'src/components/EvidenceTemplateSelectionModal.vue',
  'src/components/TemplateFolderTree.vue',
  'src/components/EvidenceList.vue',
  'src/views/CaseDashboard.vue',
  'src/composables/useEvidenceTemplates.js',
  'src/services/system.js',
  'src/services/evidence.js',
  'src/services/case.js',
]

const baseline = JSON.parse(
  readFileSync(new URL('./coverage.audit-baseline.json', import.meta.url), 'utf8'),
)

export default mergeConfig(
  vitestConfig,
  defineConfig({
    test: {
      include: auditedTests,
      coverage: {
        provider: 'v8',
        all: true,
        include: auditedSources,
        exclude: ['**/__tests__/**', '**/__mocks__/**', '**/node_modules/**', '**/dist/**'],
        reportsDirectory: 'coverage/audit',
        reporter: ['text', 'html', 'json-summary'],
        thresholds: { ...baseline.total, ...baseline.files },
      },
    },
  }),
)
