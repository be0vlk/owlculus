import { ref, nextTick, computed, watch, onScopeDispose } from 'vue'
import { useActiveCaseStore } from '@/stores/activeCase'
import { strixyService } from '@/services/strixy'
import { systemService } from '@/services/system'
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
  const { showError } = useNotifications()

  const addMessage = (message, role) => {
    messages.value.push({
      content: message,
      role,
      timestamp: new Date(),
    })
  }

  const sendMessage = async () => {
    if (!contextReady.value || !currentMessage.value.trim() || loading.value || apiKeyError.value)
      return

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

  const checkApiKeyStatus = async () => {
    const requestGeneration = generation
    try {
      const status = await systemService.checkApiKeyStatus('openai')
      if (requestGeneration !== generation) return
      apiKeyError.value = !status.is_configured
      if (!status.is_configured) {
        showError('OpenAI API key not configured. Please contact your administrator.')
      }
    } catch (error) {
      if (requestGeneration !== generation) return
      // Investigators cannot read administrator configuration. The chat endpoint
      // remains authoritative about whether a model key is configured.
      if (error.response?.status === 403) return
      console.error('Error checking OpenAI API key status:', error)
      apiKeyError.value = true
      showError('Unable to verify OpenAI API key status. Please contact your administrator.')
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
    await checkApiKeyStatus()
  }

  const clearChat = async () => {
    generation++
    messages.value = []
    currentMessage.value = ''
    loading.value = false
    apiKeyError.value = false
    await initializeChat()
  }

  watch(() => activeCase.activeCaseId, clearChat, { flush: 'sync' })

  return {
    contextReady,
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
