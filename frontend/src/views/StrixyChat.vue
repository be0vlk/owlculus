<template>
  <v-app>
    <Sidebar />
    <v-main>
      <v-container fluid class="pa-6">

        <v-alert
          v-if="apiKeyError"
          type="warning"
          variant="tonal"
          class="mb-6"
          prominent
        >
          <v-alert-title>OpenAI API Key Required</v-alert-title>
          <div>
            Strixy requires an OpenAI API key to function. Please contact your administrator to configure the OpenAI API key in the system settings.
          </div>
          <template #append>
            <v-icon size="large">mdi-key-alert</v-icon>
          </template>
        </v-alert>

        <v-card variant="outlined" class="chat-container">
          <v-card-title class="d-flex align-center pa-4 bg-surface">
            <v-icon icon="mdi-robot" color="primary" size="large" class="me-3" />
            <div class="flex-grow-1">
              <div class="text-h6 font-weight-bold">Chat Interface</div>
            </div>
            <v-tooltip text="Start new chat" location="bottom">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-plus"
                  variant="outlined"
                  :disabled="loading"
                  @click="handleNewChat"
                />
              </template>
            </v-tooltip>
          </v-card-title>

          <v-divider />

          <v-card-text class="pa-0">
            <div
              class="chat-messages pa-4"
              style="height: 500px; overflow-y: auto;"
              ref="chatContainer"
            >
              <v-list class="pa-0">
                <v-list-item
                  v-for="(message, index) in messages"
                  :key="index"
                  class="px-0 mb-3"
                >
                  <div
                    class="message-bubble"
                    :class="{
                      'user-message': message.role === 'user',
                      'assistant-message': message.role === 'assistant'
                    }"
                  >
                    <div class="message-header d-flex align-center mb-1">
                      <v-icon
                        :icon="message.role === 'user' ? 'mdi-account' : 'mdi-robot'"
                        :color="message.role === 'user' ? 'primary' : 'secondary'"
                        size="small"
                        class="me-2"
                      />
                      <span class="text-caption font-weight-medium">
                        {{ message.role === 'user' ? 'You' : 'Strixy' }}
                      </span>
                      <v-spacer />
                      <span class="text-caption text-medium-emphasis">
                        {{ formatTime(message.timestamp) }}
                      </span>
                    </div>
                    <div class="message-content">
                      {{ message.content }}
                    </div>
                  </div>
                </v-list-item>
              </v-list>

              <div v-if="loading" class="d-flex justify-center my-4">
                <v-progress-circular
                  indeterminate
                  color="primary"
                  size="24"
                  class="me-2"
                />
                <span class="text-caption">Strixy is thinking...</span>
              </div>
            </div>

            <v-divider />

            <div class="pa-4">
              <v-row no-gutters align="center">
                <v-col>
                  <v-text-field
                    v-model="currentMessage"
                    placeholder="Ask Strixy for help on your case"
                    variant="outlined"
                    density="comfortable"
                    hide-details
                    :disabled="loading || apiKeyError"
                    @keydown.enter="sendMessage"
                    aria-label="Message input"
                  />
                </v-col>
                <v-col cols="auto" class="ml-3">
                  <v-btn
                    color="primary"
                    icon="mdi-send"
                    :loading="loading"
                    :disabled="!currentMessage.trim() || loading || apiKeyError"
                    @click="sendMessage"
                    aria-label="Send message"
                  />
                </v-col>
              </v-row>
            </div>
          </v-card-text>
        </v-card>
      </v-container>
    </v-main>

    <!-- Confirmation Dialog -->
    <ConfirmationDialog ref="confirmDialog" />
  </v-app>
</template>

<script setup>
import { onMounted, computed, ref } from 'vue'
import Sidebar from '@/components/Sidebar.vue'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'
import { useStrixyChat } from '@/composables/useStrixyChat'

const {
  messages,
  loading,
  currentMessage,
  apiKeyError,
  sendMessage,
  initializeChat,
  clearChat
} = useStrixyChat()

const confirmDialog = ref(null)

const hasUserMessages = computed(() => {
  return messages.value.some(message => message.role === 'user')
})

const handleNewChat = async () => {
  if (hasUserMessages.value) {
    const confirmed = await confirmDialog.value.confirm({
      title: 'Start New Chat',
      message: 'Are you sure you want to start a new chat? This will clear your current conversation.',
      icon: 'mdi-chat-plus',
      iconColor: 'primary',
      confirmText: 'Start New Chat',
      confirmColor: 'primary'
    })
    if (confirmed) {
      clearChat()
    }
  } else {
    clearChat()
  }
}

const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(() => {
  initializeChat()
})
</script>

<style scoped>
.chat-container {
  max-width: 100%;
}

.chat-messages {
  scroll-behavior: smooth;
}

.message-bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 12px;
  background-color: rgb(var(--v-theme-surface-variant));
  margin-bottom: 8px;
}

.user-message {
  margin-left: auto;
  background-color: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}

.user-message .message-header {
  color: rgb(var(--v-theme-on-primary));
  opacity: 0.9;
}

.assistant-message {
  margin-right: auto;
  background-color: rgb(var(--v-theme-surface-variant));
  color: rgb(var(--v-theme-on-surface-variant));
}

.message-content {
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
}

@media (max-width: 600px) {
  .message-bubble {
    max-width: 95%;
  }

  .chat-messages {
    height: 400px !important;
  }
}
</style>
