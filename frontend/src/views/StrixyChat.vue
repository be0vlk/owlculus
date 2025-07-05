<template>
  <div>
    <Sidebar />
    <v-main>
      <v-container fluid class="pa-6">
        <v-alert v-if="apiKeyError" class="mb-6" prominent type="warning" variant="tonal">
          <v-alert-title>OpenAI API Key Required</v-alert-title>
          <div>
            Strixy requires an OpenAI API key to function. Please contact your administrator to
            configure the OpenAI API key in the system settings.
          </div>
          <template #append>
            <v-icon size="large">mdi-key-alert</v-icon>
          </template>
        </v-alert>

        <v-card variant="outlined" class="chat-container" :class="{ 'chat-disabled': apiKeyError }">
          <v-card-title class="d-flex align-center pa-4 bg-surface">
            <v-icon
              :color="apiKeyError ? 'grey' : 'primary'"
              class="me-3"
              icon="mdi-robot"
              size="large"
            />
            <div class="flex-grow-1">
              <div :class="{ 'text-disabled': apiKeyError }" class="text-h6 font-weight-bold">
                Chat Interface
              </div>
            </div>

            <v-tooltip text="Export chat" location="bottom">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon="mdi-download"
                  variant="tonal"
                  color="primary"
                  :disabled="!hasUserMessages || loading"
                  @click="exportChat"
                  class="mr-2"
                />
              </template>
            </v-tooltip>

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
              style="height: 500px; overflow-y: auto"
              ref="chatContainer"
            >
              <v-list class="pa-0">
                <v-list-item v-for="(message, index) in messages" :key="index" class="px-0 mb-3">
                  <div
                    class="message-bubble"
                    :class="{
                      'user-message': message.role === 'user',
                      'assistant-message': message.role === 'assistant',
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
                    <div class="message-content" v-html="renderMarkdown(message.content)"></div>
                  </div>
                </v-list-item>
              </v-list>

              <div v-if="loading" class="d-flex justify-center my-4">
                <v-progress-circular class="me-2" color="primary" indeterminate size="24" />
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
  </div>
</template>

<script setup>
import { onMounted, computed, ref } from 'vue'
import Sidebar from '@/components/Sidebar.vue'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'
import { useStrixyChat } from '@/composables/useStrixyChat'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
})

const { messages, loading, currentMessage, apiKeyError, sendMessage, initializeChat, clearChat } =
  useStrixyChat()

const confirmDialog = ref(null)

const hasUserMessages = computed(() => {
  return messages.value.some((message) => message.role === 'user')
})

const handleNewChat = async () => {
  if (hasUserMessages.value) {
    const confirmed = await confirmDialog.value.confirm({
      title: 'Start New Chat',
      message:
        'Are you sure you want to start a new chat? This will clear your current conversation.',
      icon: 'mdi-chat-plus',
      iconColor: 'primary',
      confirmText: 'Start New Chat',
      confirmColor: 'primary',
    })
    if (confirmed) {
      await clearChat()
    }
  } else {
    await clearChat()
  }
}

const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

const exportChat = () => {
  if (!hasUserMessages.value) return

  const exportData = {
    title: 'Strixy Chat Export',
    exportTime: new Date().toISOString(),
    messages: messages.value.map((msg) => ({
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp,
    })),
  }

  const dataStr = JSON.stringify(exportData, null, 2)
  const dataBlob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(dataBlob)

  const link = document.createElement('a')
  link.href = url
  link.download = `strixy_chat_${Date.now()}.json`
  link.click()

  URL.revokeObjectURL(url)
}

const renderMarkdown = (content) => {
  if (!content) return ''
  return md.render(content)
}

onMounted(async () => {
  await initializeChat()
})
</script>

<style scoped>
.chat-container {
  max-width: 100%;
}

.chat-disabled {
  opacity: 0.6;
  pointer-events: none;
  position: relative;
}

.chat-disabled::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(var(--v-theme-surface), 0.3);
  z-index: 1;
  pointer-events: none;
}

.text-disabled {
  color: rgb(var(--v-theme-on-surface-variant)) !important;
  opacity: 0.6;
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
  word-wrap: break-word;
}

/* Markdown styling */
.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3),
.message-content :deep(h4),
.message-content :deep(h5),
.message-content :deep(h6) {
  margin: 0.5em 0 0.3em 0;
  font-weight: 600;
}

.message-content :deep(h1) {
  font-size: 1.5em;
}
.message-content :deep(h2) {
  font-size: 1.3em;
}
.message-content :deep(h3) {
  font-size: 1.1em;
}

.message-content :deep(p) {
  margin: 0.5em 0;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.message-content :deep(li) {
  margin: 0.2em 0;
}

.message-content :deep(blockquote) {
  border-left: 4px solid rgb(var(--v-theme-primary));
  margin: 0.5em 0;
  padding: 0.5em 0 0.5em 1em;
  background-color: rgba(var(--v-theme-surface-variant), 0.3);
  border-radius: 4px;
}

.message-content :deep(code) {
  background-color: rgba(var(--v-theme-surface-variant), 0.8);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
}

.message-content :deep(pre) {
  background-color: rgba(var(--v-theme-surface-variant), 0.8);
  border-radius: 6px;
  padding: 1em;
  overflow-x: auto;
  margin: 0.5em 0;
}

.message-content :deep(pre code) {
  background: none;
  padding: 0;
}

.message-content :deep(a) {
  color: rgb(var(--v-theme-primary));
  text-decoration: underline;
}

.message-content :deep(strong) {
  font-weight: 600;
}

.message-content :deep(em) {
  font-style: italic;
}

.message-content :deep(table) {
  border-collapse: collapse;
  margin: 0.5em 0;
  width: 100%;
}

.message-content :deep(th),
.message-content :deep(td) {
  border: 1px solid rgba(var(--v-theme-outline), 0.3);
  padding: 0.5em;
  text-align: left;
}

.message-content :deep(th) {
  background-color: rgba(var(--v-theme-surface-variant), 0.5);
  font-weight: 600;
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
