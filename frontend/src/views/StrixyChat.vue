<template>
  <div>
    <v-main>
      <v-container fluid class="pa-6">
        <v-alert v-if="availabilityError" class="mb-6" type="warning" variant="tonal">
          <v-alert-title>Strixy unavailable</v-alert-title>
          {{ availabilityError }}
          <v-btn variant="text" :loading="checkingAvailability" @click="initializeChat">
            Check again
          </v-btn>
        </v-alert>
        <v-alert v-if="apiKeyError" class="mb-6" prominent type="warning" variant="tonal">
          <v-alert-title>OpenAI API Key Required</v-alert-title>
          <div>
            Strixy requires an OpenAI API key to function. Please contact your administrator to
            configure the OpenAI API key in the system settings.
          </div>
          <v-btn variant="text" :loading="checkingAvailability" @click="initializeChat">
            Check again
          </v-btn>
        </v-alert>

        <v-select
          :model-value="conversationId"
          :items="
            conversations.map((item, index) => ({
              title: `Conversation ${conversations.length - index} · ${new Date(item.created_at).toLocaleString()}`,
              value: item.id,
            }))
          "
          label="Private conversations"
          @update:model-value="selectConversation"
        />
        <v-alert v-if="operationError" type="warning" class="mb-4">
          {{ operationError }}
          <v-btn variant="text" @click="selectConversation(conversationId)"
            >Reopen conversation</v-btn
          >
        </v-alert>
        <v-card variant="outlined" class="chat-container">
          <v-card-title class="d-flex align-center pa-4 bg-surface">
            <v-icon
              :color="apiKeyError ? 'grey' : 'primary'"
              class="me-3"
              icon="mdi-robot"
              size="large"
            />
            <div class="flex-grow-1">
              <div
                :class="{ 'text-disabled': apiKeyError }"
                class="text-title-large font-weight-bold"
              >
                Strixy · {{ activeCase.activeCase?.case_number }}
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
                  :disabled="!canChat"
                  aria-label="Start new conversation"
                  @click="handleNewChat"
                />
              </template>
            </v-tooltip>
            <v-btn
              icon="mdi-delete"
              variant="text"
              aria-label="Delete conversation"
              :disabled="!conversationId"
              @click="handleDelete"
            />
          </v-card-title>
          <v-card-subtitle class="py-2"
            >Private to you. Case records and attachments have not been inspected.</v-card-subtitle
          >
          <v-alert v-if="runExplanation" variant="tonal" class="ma-4" role="status">{{
            runExplanation
          }}</v-alert>
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
                      <span class="text-body-small font-weight-medium">
                        {{ message.role === 'user' ? 'You' : 'Strixy' }}
                      </span>
                      <v-spacer />
                      <span class="text-body-small text-medium-emphasis">
                        {{ formatTime(message.timestamp) }}
                      </span>
                    </div>
                    <div class="message-content" v-html="renderMarkdown(message.content)"></div>
                  </div>
                </v-list-item>
              </v-list>

              <div v-if="loading" class="d-flex justify-center my-4">
                <v-progress-circular class="me-2" color="primary" indeterminate size="24" />
                <span class="text-body-small">Strixy is thinking...</span>
              </div>
            </div>

            <v-divider />

            <div class="pa-4">
              <v-row class="align-center" no-gutters>
                <v-col>
                  <v-text-field
                    v-model="currentMessage"
                    placeholder="Ask Strixy for help on your case"
                    variant="outlined"
                    density="comfortable"
                    hide-details
                    :disabled="!canChat || loading || apiKeyError"
                    @keydown.enter="sendMessage"
                    aria-label="Message input"
                  />
                </v-col>
                <v-col cols="auto" class="ml-3">
                  <v-btn
                    color="primary"
                    icon="mdi-send"
                    :loading="loading"
                    :disabled="!canChat || !currentMessage.trim() || loading || apiKeyError"
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
import { useActiveCaseStore } from '@/stores/activeCase'
import { onMounted, computed, ref } from 'vue'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'
import { useStrixyChat } from '@/composables/useStrixyChat'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
})

const activeCase = useActiveCaseStore()
const {
  canChat,
  availabilityError,
  checkingAvailability,
  messages,
  loading,
  currentMessage,
  apiKeyError,
  sendMessage,
  initializeChat,
  createConversation,
  conversations,
  conversationId,
  selectConversation,
  deleteConversation,
  operationError,
  runExplanation,
} = useStrixyChat()

const confirmDialog = ref(null)

const hasUserMessages = computed(() => {
  return messages.value.some((message) => message.role === 'user')
})

const handleNewChat = async () => {
  await createConversation()
}

const handleDelete = async () => {
  const confirmed = await confirmDialog.value.confirm({
    title: 'Delete conversation',
    message:
      'Remove this conversation and its replies from Owlculus? This does not change the provider’s independent retention policies.',
    icon: 'mdi-delete',
    confirmText: 'Delete',
    confirmColor: 'error',
  })
  if (confirmed) await deleteConversation()
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
    case_id: activeCase.activeCaseId,
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
  inset: 0;
  background-color: rgb(var(--v-theme-surface), 0.3);
  z-index: 1;
  pointer-events: none;
}

.text-disabled {
  color: rgb(var(--v-theme-on-surface-variant));
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
  margin: 0.5em 0 0.3em;
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
  background-color: rgb(var(--v-theme-surface-variant), 0.3);
  border-radius: 4px;
}

.message-content :deep(code) {
  background-color: rgb(var(--v-theme-surface-variant), 0.8);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
}

.message-content :deep(pre) {
  background-color: rgb(var(--v-theme-surface-variant), 0.8);
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
  border: 1px solid rgb(var(--v-theme-outline), 0.3);
  padding: 0.5em;
  text-align: left;
}

.message-content :deep(th) {
  background-color: rgb(var(--v-theme-surface-variant), 0.5);
  font-weight: 600;
}

@media (width <= 600px) {
  .message-bubble {
    max-width: 95%;
  }

  .chat-messages {
    height: 400px;
  }
}
</style>
