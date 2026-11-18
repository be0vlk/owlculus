import { ref, nextTick, computed, watch, onScopeDispose } from 'vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import { strixyService } from '@/services/strixy'

export function useStrixyChat() {
  const activeCase = useActiveCaseStore()
  const contextReady = computed(() => !!activeCase.activeCaseId && !activeCase.refreshing)
  const conversations = ref([])
  const conversationId = ref(null)
  const messages = ref([])
  const runs = ref([])
  const shares = ref([])
  const sharedSnapshot = ref(null)
  const shareError = ref('')
  const sharing = ref(false)
  const sourcePreview = ref(null)
  const sourceError = ref('')
  const sending = ref(false)
  const currentMessage = ref('')
  const apiKeyError = ref(false)
  const providerName = ref('LLM provider')
  const availabilityError = ref('')
  const operationError = ref('')
  const checkingAvailability = ref(false)
  const availabilityChecked = ref(false)
  let generation = 0
  let observation = 0
  let timer
  const latestRun = computed(() => runs.value.at(-1))
  const visibleMessages = computed(
    () =>
      sharedSnapshot.value?.messages ||
      [
        ...messages.value,
        ...runs.value
          .filter((run) => run.partial)
          .map((run) => ({
            ...run.partial,
            position: run.position + 0.5,
          })),
      ].sort((a, b) => a.position - b.position),
  )
  const loading = computed(
    () => sending.value || ['pending', 'running'].includes(latestRun.value?.status),
  )
  const canChat = computed(
    () =>
      !sharedSnapshot.value &&
      contextReady.value &&
      availabilityChecked.value &&
      !checkingAvailability.value &&
      !apiKeyError.value &&
      !availabilityError.value,
  )
  const coverageLimits = (coverage) =>
    (coverage?.limits || [])
      .map(
        (limit) =>
          ({
            source_count_limit: 'Record count limit reached.',
            source_scan_limit: 'Record scan limit reached.',
            source_bytes_limit: 'Source size limit reached.',
            source_field_limit: 'Record text limit reached.',
          })[limit] || 'Processing limit reached.',
      )
      .join(' ')
  const invalidate = () => {
    generation++
    observation++
    clearTimeout(timer)
    sourcePreview.value = null
    sourceError.value = ''
    sending.value = false
    sharing.value = false
    sharedSnapshot.value = null
    shares.value = []
    shareError.value = ''
  }
  onScopeDispose(invalidate)
  const scrollToBottom = () => {
    window.scrollTo({ top: document.documentElement.scrollHeight })
  }
  const clearPrivateContent = () => {
    messages.value = []
    runs.value = []
    sharedSnapshot.value = null
    shares.value = []
    conversations.value = []
    sourcePreview.value = null
  }
  const handleError = async (error, caseId) => {
    const status = error.response?.status
    if (
      status === 403 &&
      ['strixy_not_assigned', 'strixy_unavailable'].includes(error.response?.data?.code)
    ) {
      availabilityError.value = error.response.data.detail
      clearPrivateContent()
    } else if ([401, 403].includes(status)) {
      clearPrivateContent()
      availabilityError.value = 'This case is unavailable or you no longer have access.'
      await activeCase.recoverUnavailable(caseId)
    } else if (status === 422 && error.response?.data?.detail?.includes('API key not configured')) {
      apiKeyError.value = true
      operationError.value = `Ask an administrator to configure the ${providerName.value} API key, then try again.`
    } else if (status === 429 && error.response?.data?.detail) {
      operationError.value = error.response.data.detail
    } else {
      operationError.value =
        status === 409
          ? 'A reply is already in progress. Reopen the conversation to recover it.'
          : 'Unable to update this conversation. Reopen it to check whether your message was accepted before trying again.'
    }
  }

  const refresh = async (token = generation) => {
    const revision = ++observation
    clearTimeout(timer)
    const caseId = activeCase.activeCaseId
    const id = conversationId.value
    if (!id) return
    try {
      const saved = await strixyService.read(caseId, id)
      if (token !== generation || revision !== observation) return
      messages.value = saved.messages
      runs.value = saved.runs
      operationError.value = ''
      await nextTick()
      if (token !== generation || revision !== observation) return
      scrollToBottom()
      if (loading.value) timer = setTimeout(() => refresh(token), 1000)
    } catch (error) {
      if (token !== generation || revision !== observation) return
      if (error.response?.status === 404) {
        messages.value = []
        runs.value = []
        conversationId.value = null
      }
      await handleError(error, caseId)
    }
  }

  const selectConversation = async (id) => {
    invalidate()
    conversationId.value = id
    currentMessage.value = ''
    messages.value = []
    runs.value = []
    operationError.value = ''
    const token = generation
    const caseId = activeCase.activeCaseId
    await refresh()
    if (!id || token !== generation) return
    try {
      const saved = await strixyService.shares(caseId, id)
      if (token === generation) shares.value = Array.isArray(saved) ? saved : []
    } catch {
      if (token === generation) shareError.value = 'Unable to load snapshots.'
    }
  }
  const checkAvailability = async () => {
    if (!contextReady.value) return
    const token = generation
    const caseId = activeCase.activeCaseId
    checkingAvailability.value = true
    availabilityChecked.value = false
    try {
      const status = await strixyService.getAvailability(caseId)
      if (token !== generation) return
      apiKeyError.value = !status.is_configured
      providerName.value = status.provider || 'LLM provider'
      availabilityError.value = ''
      availabilityChecked.value = true
    } catch (error) {
      if (token !== generation) return
      await handleError(error, caseId)
      if (!availabilityError.value)
        availabilityError.value = 'Unable to check Strixy availability. Please try again.'
    } finally {
      if (token === generation) checkingAvailability.value = false
    }
  }
  const initializeChat = async () => {
    const token = generation
    const caseId = activeCase.activeCaseId
    await checkAvailability()
    if (token !== generation || !availabilityChecked.value) return
    try {
      const saved = await strixyService.list(caseId)
      if (token !== generation) return
      conversations.value = saved
      if (saved.length) await selectConversation(saved[0].id)
    } catch (error) {
      if (token === generation) await handleError(error, caseId)
    }
  }
  const refreshConversations = async () => {
    const token = generation
    const caseId = activeCase.activeCaseId
    try {
      const saved = await strixyService.list(caseId)
      if (token === generation) conversations.value = saved
    } catch (error) {
      if (token === generation) {
        conversations.value = []
        await handleError(error, caseId)
      }
    }
  }
  const createConversation = async () => {
    if (!contextReady.value || availabilityError.value) return
    invalidate()
    const token = generation
    const caseId = activeCase.activeCaseId
    try {
      const created = await strixyService.create(caseId)
      if (token !== generation) return
      conversations.value.unshift(created)
      await selectConversation(created.id)
    } catch (error) {
      if (token === generation) await handleError(error, caseId)
    }
  }
  const deleteConversation = async () => {
    if (!conversationId.value) return
    invalidate()
    const token = generation
    const caseId = activeCase.activeCaseId
    const id = conversationId.value
    try {
      await strixyService.remove(caseId, id)
      if (token !== generation) return
      conversations.value = conversations.value.filter((item) => item.id !== id)
      await selectConversation(conversations.value[0]?.id || null)
    } catch (error) {
      if (token === generation) await handleError(error, caseId)
    }
  }
  const sendMessage = async () => {
    if (!canChat.value || !currentMessage.value.trim() || loading.value) return
    const content = currentMessage.value.trim()
    const token = generation
    const caseId = activeCase.activeCaseId
    sending.value = true
    operationError.value = ''
    try {
      if (!conversationId.value) {
        const created = await strixyService.create(caseId)
        if (token !== generation) return
        conversationId.value = created.id
        conversations.value.unshift(created)
      }
      const run = await strixyService.sendMessage(content, caseId, conversationId.value)
      if (token !== generation) return
      runs.value.push(run)
      currentMessage.value = ''
      sending.value = false
      await refresh(token)
    } catch (error) {
      if (token === generation) await handleError(error, caseId)
    } finally {
      if (token === generation) sending.value = false
    }
  }
  const controlRun = async (action) => {
    if (!canChat.value || !latestRun.value || sending.value) return
    const token = generation
    const caseId = activeCase.activeCaseId
    const id = conversationId.value
    const runId = latestRun.value.id
    observation++
    sending.value = true
    clearTimeout(timer)
    try {
      await strixyService.control(caseId, id, runId, action)
      if (token !== generation) return
      sending.value = false
      await refresh(token)
    } catch (error) {
      if (token === generation) await handleError(error, caseId)
    } finally {
      if (token === generation) sending.value = false
    }
  }
  const createShare = async (throughMessageId) => {
    if (!conversationId.value || sharing.value) return
    const token = generation
    const caseId = activeCase.activeCaseId
    sharing.value = true
    shareError.value = ''
    try {
      const saved = await strixyService.share(caseId, conversationId.value, throughMessageId)
      if (token === generation) shares.value.push(saved)
    } catch {
      if (token === generation)
        shareError.value =
          'Unable to share these messages. Reopen the conversation to check current access.'
    } finally {
      if (token === generation) sharing.value = false
    }
  }
  const revokeShare = async (id) => {
    const token = generation
    const caseId = activeCase.activeCaseId
    try {
      await strixyService.revokeShare(caseId, id)
      if (token === generation) shares.value = shares.value.filter((s) => s.id !== id)
    } catch {
      if (token === generation)
        shareError.value = 'Unable to revoke this snapshot. Reopen to check its status.'
    }
  }
  const openShare = async (id) => {
    if (!contextReady.value || !id) return
    invalidate()
    conversationId.value = null
    messages.value = []
    runs.value = []
    currentMessage.value = ''
    const token = generation
    const caseId = activeCase.activeCaseId
    try {
      const saved = await strixyService.readShare(caseId, id)
      if (token === generation) sharedSnapshot.value = saved
    } catch {
      if (token === generation)
        shareError.value =
          'Snapshot unavailable. It may have been revoked, deleted, or access may have changed.'
    }
  }
  const copyShare = async () => {
    if (!sharedSnapshot.value || sharing.value) return
    const token = generation
    const caseId = activeCase.activeCaseId
    const id = sharedSnapshot.value.id
    sharing.value = true
    try {
      const created = await strixyService.copyShare(caseId, id)
      if (token !== generation) return
      conversations.value.unshift(created)
      await selectConversation(created.id)
    } catch {
      if (token === generation) {
        sharedSnapshot.value = null
        shareError.value =
          'Unable to start a follow-up. The snapshot or required access is unavailable.'
      }
    } finally {
      if (token === generation) sharing.value = false
    }
  }
  const openSource = async (citation) => {
    const token = generation
    const caseId = activeCase.activeCaseId
    sourcePreview.value = null
    sourceError.value = ''
    try {
      const page = /^attachment:page:(\d+):/.exec(citation.field || '')
      const source = await strixyService.source(
        caseId,
        citation.source_id,
        page ? Number(page[1]) : undefined,
      )
      if (token !== generation) return
      sourcePreview.value = { ...source, citation }
    } catch (error) {
      if (token === generation)
        sourceError.value =
          error.response?.status === 503
            ? 'Too many previews are loading. Try again in a moment.'
            : 'This source is unavailable or your access has changed.'
    }
  }
  const authorizedExport = async () => {
    const token = generation
    const caseId = activeCase.activeCaseId
    const id = conversationId.value
    if (!id) return null
    try {
      const saved = await strixyService.read(caseId, id)
      if (token !== generation) return null
      messages.value = saved.messages
      runs.value = saved.runs
      return saved
    } catch (error) {
      if (token === generation) await handleError(error, caseId)
      return null
    }
  }
  watch(
    () => activeCase.activeCaseId,
    async () => {
      invalidate()
      conversationId.value = null
      clearPrivateContent()
      currentMessage.value = ''
      availabilityError.value = ''
      operationError.value = ''
      availabilityChecked.value = false
      apiKeyError.value = false
      checkingAvailability.value = false
      await initializeChat()
    },
    { flush: 'sync' },
  )

  watch(
    contextReady,
    async (ready) => {
      if (ready && !availabilityChecked.value && !checkingAvailability.value) await initializeChat()
    },
    { flush: 'sync' },
  )

  return {
    shares,
    sharedSnapshot,
    shareError,
    sharing,
    createShare,
    revokeShare,
    openShare,
    copyShare,
    latestRun,
    coverageLimits,
    visibleMessages,
    controlRun,
    refreshConversations,
    sourcePreview,
    sourceError,
    openSource,
    authorizedExport,
    canChat,
    availabilityError,
    operationError,
    checkingAvailability,
    conversations,
    conversationId,
    selectConversation,
    deleteConversation,
    messages,
    loading,
    currentMessage,
    apiKeyError,
    providerName,
    sendMessage,
    initializeChat,
    createConversation,
  }
}
