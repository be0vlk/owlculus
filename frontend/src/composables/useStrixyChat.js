import { ref, nextTick, computed, watch, onScopeDispose } from 'vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import { strixyService } from '@/services/strixy'
import { useNotifications } from './useNotifications'

export function useStrixyChat() {
  const activeCase = useActiveCaseStore()
  const contextReady = computed(() => !!activeCase.activeCaseId && !activeCase.refreshing)
  let generation = 0
  onScopeDispose(() => {
    generation++
  })
  const messages = ref([])
  const loading = ref(false)
  const currentMessage = ref('')
  const apiKeyError = ref(false)
  const availabilityError = ref('')
  const checkingAvailability = ref(false)
  const availabilityChecked = ref(false)
  const canChat = computed(
    () =>
      contextReady.value &&
      availabilityChecked.value &&
      !checkingAvailability.value &&
      !apiKeyError.value &&
      !availabilityError.value,
  )
  const { showError } = useNotifications()

  const addMessage = (message, role) => {
    messages.value.push({
      content: message,
      role,
      timestamp: new Date(),
    })
  }

  const sendMessage = async () => {
    if (!canChat.value || !currentMessage.value.trim() || loading.value) return

    const requestGeneration = generation
    const caseId = activeCase.activeCaseId

    const userMessage = currentMessage.value.trim()
    addMessage(userMessage, 'user')
    currentMessage.value = ''
    loading.value = true

    try {
      const chatMessages = messages.value.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }))

      const response = await strixyService.sendMessage(chatMessages, caseId)
      if (requestGeneration !== generation) return
      addMessage(response.message, 'assistant')

      await nextTick()
      scrollToBottom()
    } catch (error) {
      if (requestGeneration !== generation) return
      console.error('Error sending message:', error)
      if (isStrixyUnavailable(error)) {
        availabilityError.value = error.response.data.detail
        return
      }
      if ([403, 404].includes(error.response?.status)) {
        await activeCase.recoverUnavailable(caseId)
        return
      }

      // Check if it's an API key configuration error
      if (
        [400, 422].includes(error.response?.status) &&
        error.response?.data?.detail?.includes('OpenAI API key not configured')
      ) {
        apiKeyError.value = true
        showError('OpenAI API key not configured. Please contact your administrator.')
      } else {
        showError('Failed to send message to Strixy. Please try again.')
      }
    } finally {
      if (requestGeneration === generation) loading.value = false
    }
  }

  const scrollToBottom = () => {
    const chatContainer = document.querySelector('.chat-messages')
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight
    }
  }

  const isStrixyUnavailable = (error) =>
    error.response?.status === 403 &&
    ['strixy_not_assigned', 'strixy_unavailable'].includes(error.response?.data?.code)

  const checkAvailability = async () => {
    if (!contextReady.value) return
    const requestGeneration = generation
    const caseId = activeCase.activeCaseId
    checkingAvailability.value = true
    try {
      const status = await strixyService.getAvailability(caseId)
      if (requestGeneration !== generation) return
      availabilityError.value = ''
      apiKeyError.value = !status.is_configured
      availabilityChecked.value = true
    } catch (error) {
      if (requestGeneration !== generation) return
      if (isStrixyUnavailable(error)) {
        availabilityError.value = error.response.data.detail
      } else if ([403, 404].includes(error.response?.status)) {
        availabilityError.value = 'This case is unavailable or you no longer have access.'
        await activeCase.recoverUnavailable(caseId)
      } else {
        availabilityError.value = 'Unable to check Strixy availability. Please try again.'
      }
    } finally {
      if (requestGeneration === generation) checkingAvailability.value = false
    }
  }

  const initializeChat = async () => {
    if (!contextReady.value) return
    if (messages.value.length === 0) {
      addMessage(
        "Hello! I'm Strixy, your Owlculus Toolkit OSINT assistant. How can I help?",
        'assistant',
      )
    }
    await checkAvailability()
  }

  const clearChat = async () => {
    generation++
    messages.value = []
    currentMessage.value = ''
    loading.value = false
    apiKeyError.value = false
    availabilityError.value = ''
    availabilityChecked.value = false
    checkingAvailability.value = false
    await initializeChat()
  }

  watch(() => activeCase.activeCaseId, clearChat, { flush: 'sync' })

  return {
    contextReady,
    canChat,
    availabilityError,
    checkingAvailability,
    checkAvailability,
    messages,
    loading,
    currentMessage,
    apiKeyError,
    sendMessage,
    initializeChat,
    clearChat,
    scrollToBottom,
  }
}
