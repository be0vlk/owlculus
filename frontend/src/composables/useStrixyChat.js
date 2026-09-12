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
  const focus = ref([])
  const sourceOptions = ref([])
  const sourcePreview = ref(null)
  const sourceError = ref('')
  const sending = ref(false)
  const currentMessage = ref('')
  const apiKeyError = ref(false)
  const availabilityError = ref('')
  const operationError = ref('')
  const checkingAvailability = ref(false)
  const availabilityChecked = ref(false)
  let generation = 0
  let timer
  const latestRun = computed(() => runs.value.at(-1))
  const loading = computed(
    () => sending.value || ['pending', 'running'].includes(latestRun.value?.status),
  )
  const canChat = computed(
    () =>
      contextReady.value &&
      availabilityChecked.value &&
      !checkingAvailability.value &&
      !apiKeyError.value &&
      !availabilityError.value,
  )
  const runExplanation = computed(() => {
    const run = latestRun.value
    if (!run) return ''
    if (run.limit_code === 'input_limit')
      return 'Conversation limit reached. No answer was generated. Start a new conversation with a shorter question.'
    if (run.limit_code === 'model_call_limit')
      return 'Analysis step limit reached. Ask a more focused question to continue.'
    if (run.error_code === 'sources_changed')
      return 'Source content or access changed during analysis. Send a new question to use current permitted records.'
    if (run.error_code === 'invalid_citation')
      return 'The reply contained an invalid source reference and was withheld. Send a new question to try again.'
    if (run.limit_code === 'output_limit')
      return 'Reply limit reached. The answer may be incomplete; send a follow-up question to continue.'
    if (run.error_code === 'completion_uncertain')
      return 'The worker stopped or timed out. Completion is uncertain, so Strixy did not automatically retry. You can send a new message.'
    if (run.error_code === 'provider_not_configured')
      return 'Ask an administrator to configure the OpenAI API key, then send a new message.'
    if (['dispatch_failed', 'worker_unavailable'].includes(run.error_code))
      return 'Background services are unavailable. Ask an administrator to check them, then send a new message.'
    if (run.status === 'failed')
      return 'Strixy could not complete this reply. Your conversation is saved; send a new message to try again.'
    if (run.status === 'cancelled') return 'This run stopped because access changed.'
    return run.status === 'pending'
      ? 'Reply queued'
      : run.status === 'running'
        ? 'Preparing reply'
        : 'Reply completed'
  })

  const invalidate = () => {
    generation++
    clearTimeout(timer)
    sourcePreview.value = null
    sourceError.value = ''
    sending.value = false
  }
  onScopeDispose(invalidate)
  const scrollToBottom = () => {
    const container = document.querySelector('.chat-messages')
    if (container) container.scrollTop = container.scrollHeight
  }
  const clearPrivateContent = () => {
    messages.value = []
    runs.value = []
    conversations.value = []
    sourcePreview.value = null
    sourceOptions.value = []
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
      operationError.value = 'Ask an administrator to configure the OpenAI API key, then try again.'
    } else {
      operationError.value =
        status === 409
          ? 'A reply is already in progress. Reopen the conversation to recover it.'
          : 'Unable to update this conversation. Reopen it to check whether your message was accepted before trying again.'
    }
  }

  const refresh = async (token = generation) => {
    const caseId = activeCase.activeCaseId
    const id = conversationId.value
    if (!id) return
    try {
      const saved = await strixyService.read(caseId, id)
      if (token !== generation) return
      messages.value = saved.messages
      runs.value = saved.runs
      operationError.value = ''
      await nextTick()
      if (token !== generation) return
      scrollToBottom()
      if (loading.value) timer = setTimeout(() => refresh(token), 1000)
    } catch (error) {
      if (token !== generation) return
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
    await refresh()
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
      const catalog = await strixyService.sources(caseId)
      if (token !== generation) return
      sourceOptions.value = catalog.sources || []
      if (saved.length) await selectConversation(saved[0].id)
    } catch (error) {
      if (token === generation) await handleError(error, caseId)
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
      const run = await strixyService.sendMessage(
        content,
        caseId,
        conversationId.value,
        focus.value,
      )
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
  const openSource = async (citation) => {
    const token = generation
    const caseId = activeCase.activeCaseId
    sourcePreview.value = null
    sourceError.value = ''
    try {
      const source = await strixyService.source(caseId, citation.source_id)
      if (token !== generation) return
      sourcePreview.value = source
    } catch {
      if (token === generation)
        sourceError.value = 'This source is unavailable or your access has changed.'
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
      focus.value = []
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
    focus,
    sourceOptions,
    sourcePreview,
    sourceError,
    openSource,
    authorizedExport,
    contextReady,
    canChat,
    availabilityError,
    operationError,
    checkingAvailability,
    checkAvailability,
    conversations,
    conversationId,
    selectConversation,
    deleteConversation,
    messages,
    runs,
    runExplanation,
    loading,
    currentMessage,
    apiKeyError,
    sendMessage,
    initializeChat,
    createConversation,
    scrollToBottom,
  }
}
