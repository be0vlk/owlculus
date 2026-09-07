import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import { useAuthStore } from '@/stores/auth'
import { useTaskStore } from '@/stores/taskStore'
import { caseService } from '@/services/case'
import { TASK_STATUS_LABELS } from '@/constants/tasks'
import { useNotifications } from './useNotifications'

export function useBulkTaskActions(displayedTasks) {
  const context = useActiveCaseStore()
  const auth = useAuthStore()
  const store = useTaskStore()
  const { snackbar, showSuccess } = useNotifications()
  const selection = ref([])
  const kind = ref(null)
  const value = ref(undefined)
  const pending = ref(false)
  const submittedCount = ref(0)
  const targetedCount = computed(() =>
    pending.value ? submittedCount.value : selected.value.length,
  )
  const feedback = ref('')
  const users = ref([])
  const usersLoading = ref(false)
  const usersError = ref('')
  const needsRefresh = ref(false)
  let generation = 0
  let userRequest = 0

  const availableIds = computed(
    () =>
      new Set(
        displayedTasks.value
          .filter((task) => task.case_id === context.activeCaseId)
          .map((task) => task.id),
      ),
  )
  const selected = computed({
    get: () => selection.value,
    set: (ids) => {
      selection.value = [...new Set(ids)].filter((id) => availableIds.value.has(id))
    },
  })
  watch(
    availableIds,
    () => {
      selected.value = [...selected.value]
    },
    { flush: 'sync' },
  )
  const member = computed(() => users.value.find((user) => user.id === auth.user?.id))
  const canUpdate = computed(
    () =>
      !!context.activeCaseId &&
      (auth.user?.role === 'Admin' || (auth.user?.role === 'Investigator' && !!member.value)),
  )
  const canAssign = computed(
    () => canUpdate.value && (auth.user?.role === 'Admin' || member.value?.is_lead === true),
  )
  const statusOptions = Object.entries(TASK_STATUS_LABELS).map(([value, title]) => ({
    value,
    title,
  }))
  // A sentinel makes unassignment an explicit choice, distinct from an untouched field.
  const assigneeOptions = computed(() => [
    { value: 'unassigned', title: 'Unassigned' },
    ...users.value.map((user) => ({ value: user.id, title: user.username })),
  ])
  const canSubmit = computed(
    () =>
      selected.value.length > 0 &&
      !pending.value &&
      !needsRefresh.value &&
      (kind.value === 'assign'
        ? canAssign.value &&
          !usersLoading.value &&
          !usersError.value &&
          assigneeOptions.value.some((option) => option.value === value.value)
        : kind.value === 'status' &&
          canUpdate.value &&
          statusOptions.some((option) => option.value === value.value)),
  )

  async function loadUsers() {
    const caseId = context.activeCaseId
    if (!caseId || !auth.user) return
    const visit = generation
    const request = ++userRequest
    usersLoading.value = true
    usersError.value = ''
    try {
      const result = await caseService.getCaseUsers(caseId)
      if (visit === generation && request === userRequest) users.value = result
    } catch {
      if (visit === generation && request === userRequest) {
        users.value = []
        usersError.value = 'Unable to load Case users. Retry to check membership and assignees.'
      }
    } finally {
      if (visit === generation && request === userRequest) usersLoading.value = false
    }
  }

  function close() {
    if (pending.value) return
    kind.value = null
    value.value = undefined
    feedback.value = ''
  }

  function open(action) {
    if (
      pending.value ||
      !selected.value.length ||
      !(action === 'assign' ? canAssign.value : canUpdate.value)
    )
      return
    kind.value = action
    value.value = undefined
    feedback.value = ''
    if (action === 'assign') loadUsers()
  }

  async function reconcile(isCurrent) {
    try {
      await store.loadTasks(null, isCurrent)
      if (!isCurrent()) return
      const detail = store.currentTask
      if (detail?.case_id === context.activeCaseId) {
        store.currentTask = store.tasks.find((task) => task.id === detail.id) || null
      }
      selected.value = [...selected.value]
      needsRefresh.value = false
    } catch {
      if (isCurrent()) {
        needsRefresh.value = true
        feedback.value += ' Unable to refresh Tasks. Refresh before retrying.'
      }
    }
  }

  async function refresh() {
    if (pending.value) return
    const visit = generation
    pending.value = true
    await reconcile(() => visit === generation)
    if (visit === generation) pending.value = false
  }

  async function submit() {
    if (!canSubmit.value) return
    const visit = generation
    const caseId = context.activeCaseId
    const ids = [...selected.value]
    submittedCount.value = ids.length
    const choice = value.value
    const isCurrent = () => visit === generation && caseId === context.activeCaseId
    pending.value = true
    feedback.value = ''
    try {
      const updated = await (kind.value === 'assign'
        ? store.bulkAssign(ids, choice === 'unassigned' ? null : choice, isCurrent)
        : store.bulkUpdateStatus(ids, choice, isCurrent))
      if (!isCurrent()) return
      const acknowledged = new Set(
        updated
          .filter((task) => task.case_id === caseId && ids.includes(task.id))
          .map((task) => task.id),
      )
      selected.value = ids.filter((id) => !acknowledged.has(id))
      if (acknowledged.size === ids.length) {
        pending.value = false
        close()
        showSuccess(`${ids.length} Tasks updated`)
      } else {
        feedback.value = `${acknowledged.size} Tasks updated; ${ids.length - acknowledged.size} not updated. Retry the remaining available Tasks.`
        await reconcile(isCurrent)
      }
    } catch (error) {
      if (!isCurrent()) return
      feedback.value = `${error.response?.data?.detail || 'Unable to confirm Task updates'}. Some Tasks may have changed. Review refreshed Tasks before retrying.`
      selected.value = ids
      await reconcile(isCurrent)
    } finally {
      if (isCurrent()) pending.value = false
    }
  }

  watch(
    [() => context.activeCaseId, () => auth.user?.id],
    () => {
      generation++
      selected.value = []
      kind.value = null
      value.value = undefined
      pending.value = false
      feedback.value = ''
      needsRefresh.value = false
      users.value = []
      usersError.value = ''
      usersLoading.value = false
      snackbar.value.show = false
      loadUsers()
    },
    { immediate: true, flush: 'sync' },
  )
  onBeforeUnmount(() => {
    generation++
  })

  return {
    selected,
    targetedCount,
    kind,
    value,
    pending,
    feedback,
    usersLoading,
    usersError,
    needsRefresh,
    canAssign,
    canUpdate,
    canSubmit,
    assigneeOptions,
    statusOptions,
    snackbar,
    open,
    close,
    submit,
    loadUsers,
    refresh,
  }
}
