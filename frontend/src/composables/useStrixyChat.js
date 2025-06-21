import { ref, nextTick } from 'vue'
import { strixyService } from '@/services/strixy'
import { systemService } from '@/services/system'
import { useNotifications } from './useNotifications'

export function useStrixyChat() {
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
    if (!currentMessage.value.trim() || loading.value) return

    const userMessage = currentMessage.value.trim()
    addMessage(userMessage, 'user')
    currentMessage.value = ''
    loading.value = true

    try {
      const chatMessages = messages.value.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }))

      const response = await strixyService.sendMessage(chatMessages)
      addMessage(response.message, 'assistant')

      await nextTick()
      scrollToBottom()
    } catch (error) {
      console.error('Error sending message:', error)

      // Check if it's an API key configuration error
      if (
        error.response?.status === 400 &&
        error.response?.data?.detail?.includes('OpenAI API key not configured')
      ) {
        apiKeyError.value = true
        showError('OpenAI API key not configured. Please contact your administrator.')
      } else {
        showError('Failed to send message to Strixy. Please try again.')
      }
    } finally {
      loading.value = false
    }
  }

  const scrollToBottom = () => {
    const chatContainer = document.querySelector('.chat-messages')
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight
    }
  }

  const checkApiKeyStatus = async () => {
    try {
      const status = await systemService.checkApiKeyStatus('openai')
      apiKeyError.value = !status.is_configured
      if (!status.is_configured) {
        showError('OpenAI API key not configured. Please contact your administrator.')
      }
    } catch (error) {
      console.error('Error checking OpenAI API key status:', error)
      apiKeyError.value = true
      showError('Unable to verify OpenAI API key status. Please contact your administrator.')
    }
  }

  const initializeChat = async () => {
    await checkApiKeyStatus()
    if (messages.value.length === 0) {
      addMessage(
        "Hello! I'm Strixy, your Owlculus Toolkit OSINT assistant. How can I help?",
        'assistant',
      )
    }
  }

  const clearChat = async () => {
    messages.value = []
    apiKeyError.value = false
    await initializeChat()
  }

  return {
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
