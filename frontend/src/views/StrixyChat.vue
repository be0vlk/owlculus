<template>
  <v-main class="strixy-page">
    <header class="strixy-header">
      <div class="strixy-brand">
        <div>
          <h1>Strixy</h1>
          <p>
            {{ activeCase.activeCase?.case_number }}
            <span class="strixy-brand-role">· Case assistant</span>
          </p>
        </div>
      </div>
      <div class="strixy-header-actions">
        <v-btn
          variant="text"
          prepend-icon="mdi-history"
          aria-label="Conversations"
          @click="openHistory"
          ><span>Conversations</span></v-btn
        >
        <v-btn
          v-if="!sharedSnapshot && shareableMessages.length"
          variant="text"
          prepend-icon="mdi-share-variant-outline"
          aria-label="Share conversation"
          :disabled="sharing"
          @click="openSharing(shareableMessages.at(-1).id)"
          ><span>Share</span></v-btn
        >
        <v-btn
          variant="outlined"
          prepend-icon="mdi-plus"
          aria-label="Start new conversation"
          :disabled="initializing || !!availabilityError || changingConversation"
          @click="handleNewChat"
          ><span>New chat</span></v-btn
        >
        <v-menu v-if="conversationId && !sharedSnapshot" location="bottom end"
          ><template #activator="{ props }"
            ><v-btn
              v-bind="props"
              icon="mdi-dots-horizontal"
              size="small"
              variant="text"
              aria-label="Conversation actions" /></template
          ><v-list>
            <v-list-item
              title="Export conversation"
              prepend-icon="mdi-download"
              :disabled="!hasUserMessages || loading"
              @click="exportChat"
            />
            <v-list-item
              v-if="latestRun"
              title="Reanalyze current data"
              prepend-icon="mdi-refresh"
              :disabled="!canChat || loading"
              @click="controlRun('reanalyze')"
            />
            <v-list-item
              title="Shared snapshots"
              prepend-icon="mdi-share-variant-outline"
              @click="sharingOpen = true"
            />
            <v-list-item
              title="Delete conversation"
              prepend-icon="mdi-delete-outline"
              :disabled="changingConversation"
              @click="handleDelete"
            /> </v-list
        ></v-menu>
      </div>
    </header>

    <section class="strixy-layout" :class="{ 'strixy-empty': !visibleMessages.length }">
      <div v-if="availabilityError || apiKeyError" class="strixy-notice" role="status">
        <v-icon icon="mdi-information-outline" size="20" />
        <div>
          <strong>{{ apiKeyError ? 'Strixy needs a connection' : 'Strixy unavailable' }}</strong>
          <p>
            {{
              apiKeyError
                ? 'Ask an administrator to configure the OpenAI API key in system settings.'
                : availabilityError
            }}
          </p>
        </div>
        <v-btn variant="text" :loading="checkingAvailability" @click="initializeChat"
          >Check again</v-btn
        >
      </div>
      <div v-if="shareError && !sharingOpen" class="strixy-notice" role="status">
        {{ shareError }}
      </div>
      <div v-if="operationError" class="strixy-notice" role="status">
        <span>{{ operationError }}</span
        ><v-btn variant="text" @click="selectConversation(conversationId)"
          >Reopen conversation</v-btn
        >
      </div>
      <div v-if="sharedSnapshot" class="strixy-notice shared-notice">
        <v-icon icon="mdi-lock-outline" size="18" />
        <div>
          <strong>Read-only snapshot</strong>
          <p>
            {{ sharedSnapshot.message_count }} messages · Shared
            {{ formatDate(sharedSnapshot.created_at) }}. Later private replies are excluded.
          </p>
        </div>
        <v-btn variant="text" :loading="sharing" @click="copyShare">Start private follow-up</v-btn>
      </div>

      <div
        class="chat-messages"
        role="log"
        aria-label="Conversation"
        aria-live="polite"
        :aria-busy="loading || initializing || changingConversation"
      >
        <div v-if="initializing || changingConversation" class="strixy-loading" role="status">
          <v-progress-circular indeterminate size="24" width="2" /> Opening conversation…
        </div>
        <div v-else-if="!visibleMessages.length && !sharedSnapshot" class="strixy-welcome">
          <p class="strixy-eyebrow">A little clarity for your case</p>
          <h2>Where should we start?</h2>
          <p class="strixy-welcome-copy">
            Ask a question. I’ll use your case records<br class="desktop-break" />
            and show you the sources.
          </p>
          <div class="strixy-starters">
            <button
              v-for="prompt in starterPrompts"
              :key="prompt.title"
              :disabled="!canChat"
              @click="startPrompt(prompt.text)"
            >
              <v-icon :icon="prompt.icon" size="22" /><strong>{{ prompt.title }}</strong
              ><span>{{ prompt.detail }}</span
              ><v-icon icon="mdi-arrow-up-right" size="16" class="starter-arrow" />
            </button>
          </div>
        </div>
        <template v-else>
          <StrixyMessage
            v-for="(message, index) in displayMessages"
            :key="message.id || index"
            :message="message"
            :shared="!!sharedSnapshot"
            :sharing="sharing"
            @source="openSource"
            @review="reviewIndex = index"
            @share="openSharing"
          />
          <div v-if="loading" class="strixy-loading" role="status">
            <v-progress-circular indeterminate size="18" width="2" />{{ progressLabel }}
          </div>
        </template>
      </div>

      <div v-if="recoveryNotice" class="strixy-notice run-notice" role="status">
        <span>{{ recoveryNotice }}</span
        ><v-btn
          v-if="canContinue"
          variant="text"
          :disabled="!canChat || loading"
          @click="controlRun('continue')"
          >Continue analysis</v-btn
        ><v-btn
          v-else-if="latestRun?.error_code === 'sources_changed'"
          variant="text"
          :disabled="!canChat || loading"
          @click="controlRun('reanalyze')"
          >Reanalyze current data</v-btn
        ><v-btn
          v-else-if="latestRun?.status === 'failed'"
          variant="text"
          :disabled="!canChat || loading"
          @click="controlRun('retry')"
          >Retry analysis</v-btn
        >
      </div>
      <div v-if="!sharedSnapshot" class="strixy-compose-area">
        <form class="strixy-composer" @submit.prevent="sendMessage">
          <textarea
            ref="messageInput"
            v-model="currentMessage"
            aria-label="Message input"
            rows="2"
            placeholder="Ask anything about this case…"
            :disabled="!canChat || initializing || changingConversation"
            @keydown="composerKeydown"
          />
          <div class="strixy-composer-tools">
            <span class="strixy-compose-hint">{{
              loading ? 'Reviewing your sources…' : 'Enter to send'
            }}</span
            ><v-btn
              v-if="loading"
              icon="mdi-stop"
              size="small"
              color="primary"
              aria-label="Cancel analysis"
              :disabled="!canChat || !['pending', 'running'].includes(latestRun?.status)"
              @click="controlRun('cancel')"
            /><v-btn
              v-else
              type="submit"
              icon="mdi-arrow-up"
              size="small"
              color="primary"
              aria-label="Send message"
              :disabled="!canChat || !currentMessage.trim() || initializing || changingConversation"
            />
          </div>
        </form>
        <p class="strixy-composer-note">
          <v-icon icon="mdi-lock-outline" size="12" />Private to you <span>·</span> Check sources
          before using a finding.
        </p>
      </div>
    </section>

    <v-dialog v-model="historyOpen" max-width="560" scrollable aria-label="Your conversations"
      ><v-card
        class="strixy-dialog"
        rounded="xl"
        title="Your conversations"
        subtitle="Private to you, within this case."
      >
        <template #append>
          <v-btn
            icon="mdi-close"
            variant="text"
            aria-label="Close conversations"
            @click="historyOpen = false"
          />
        </template>
        <div class="dialog-search">
          <v-text-field
            v-model="historyQuery"
            label="Find a conversation"
            prepend-inner-icon="mdi-magnify"
            hide-details
            clearable
          />
        </div>
        <v-card-text
          ><div v-if="historyLoading" class="strixy-loading">
            <v-progress-circular indeterminate size="20" />Loading conversations…
          </div>
          <template v-else
            ><v-list v-if="filteredConversations.length" class="pa-0">
              <v-list-item
                v-for="conversation in filteredConversations"
                :key="conversation.id"
                :title="conversation.title"
                :subtitle="formatDate(conversation.created_at)"
                prepend-icon="mdi-chat-outline"
                append-icon="mdi-chevron-right"
                lines="two"
                @click="selectConversation(conversation.id)"
              />
            </v-list>
            <p v-if="!filteredConversations.length" class="dialog-note">
              {{
                conversations.length
                  ? 'No matching conversations.'
                  : 'Your conversations will appear here.'
              }}
            </p></template
          ></v-card-text
        >
        <div class="strixy-dialog-actions">
          <v-btn
            color="primary"
            prepend-icon="mdi-plus"
            :disabled="!!availabilityError || changingConversation"
            @click="handleNewChat"
            >New conversation</v-btn
          >
        </div></v-card
      ></v-dialog
    >

    <v-dialog
      :model-value="!!reviewedMessage"
      max-width="650"
      scrollable
      aria-label="Behind this answer"
      @update:model-value="!$event && (reviewIndex = null)"
      ><v-card
        v-if="reviewedMessage"
        class="strixy-dialog"
        rounded="xl"
        title="Behind this answer"
        :subtitle="`${reviewedMessage.citations?.length || 0} source references`"
      >
        <template #append>
          <v-btn
            icon="mdi-close"
            variant="text"
            aria-label="Close review details"
            @click="reviewIndex = null"
          />
        </template>
        <v-card-text>
          <div
            v-for="(citation, index) in reviewedMessage.citations || []"
            :key="`${citation.source_id}:${citation.field}:${index}`"
            class="review-citation"
          >
            <v-list-item
              :title="sourceLabel(citation)"
              :subtitle="`${citationLocation(citation)} · Inspected ${formatDate(citation.inspected_at)}`"
              append-icon="mdi-chevron-right"
              lines="two"
              class="px-0"
              @click="inspectReviewedSource(citation)"
            >
              <template #prepend>
                <span class="review-citation-number me-3">{{ index + 1 }}</span>
              </template>
            </v-list-item>
            <p v-if="citation.kind === 'visual'" class="dialog-note">
              Visual reference; interpretation is not a verified transcription.
            </p>
            <blockquote v-else-if="citation.excerpt">{{ citation.excerpt }}</blockquote>
            <p v-if="citation.source_status === 'changed'" class="dialog-note">
              Source changed since this answer.
            </p>
          </div>
          <section v-if="reviewedMessage.coverage" class="review-coverage">
            <h3>What was reviewed</h3>
            <p>
              {{ reviewedMessage.coverage.counts?.read || 0 }} records read,
              {{ reviewedMessage.coverage.counts?.partly_read || 0 }} partly read,
              {{ reviewedMessage.coverage.counts?.unexamined || 0 }} unexamined<span
                v-if="reviewedMessage.coverage.counts?.unavailable"
                >, {{ reviewedMessage.coverage.counts.unavailable }} unavailable</span
              >.
            </p>
            <p v-if="!reviewedMessage.coverage.complete">
              <strong>Incomplete coverage.</strong> {{ coverageLimits(reviewedMessage.coverage) }}
            </p>
            <p v-if="!reviewedMessage.coverage.enumeration_complete">
              The record limit was reached; more material may exist.
            </p>
            <StrixyAttachmentCoverage
              v-if="reviewedMessage.coverage.attachment_outcomes"
              :outcomes="reviewedMessage.coverage.attachment_outcomes"
              :source-labels="sourceLabels"
            />
            <p v-else>Attachments unexamined.</p>
          </section>
          <p class="dialog-note">
            Citations verify source references, not the accuracy of every interpretation.
          </p>
        </v-card-text></v-card
      ></v-dialog
    >

    <v-dialog
      :model-value="!!sourcePreview || !!sourceError"
      max-width="720"
      scrollable
      :aria-label="sourcePreviewTitle"
      @update:model-value="closeSource"
      ><v-card
        class="strixy-dialog"
        rounded="xl"
        :title="sourcePreviewTitle"
        subtitle="Source preview"
      >
        <template #append>
          <v-btn
            icon="mdi-close"
            variant="text"
            aria-label="Close source preview"
            @click="closeSource"
          />
        </template>
        <v-card-text
          ><p v-if="sourceError" role="status">{{ sourceError }}</p>
          <template v-else-if="sourcePreview"
            ><p v-if="sourcePreview.citation?.source_status === 'changed'" class="dialog-note">
              Current file shown. This source changed since the historical answer.
            </p>
            <p class="dialog-note">{{ citationLocation(sourcePreview.citation || {}) }}</p>
            <blockquote v-if="sourcePreview.citation?.excerpt" class="source-excerpt">
              {{ sourcePreview.citation.excerpt }}
            </blockquote>
            <img
              v-for="image in sourcePreview.images || []"
              :key="image.field"
              :src="'data:image/png;base64,' + image.data"
              :alt="labelForSourcePreview + ' · ' + citationLocation(image)"
              class="source-image"
            /><template v-for="source in sourcePreview.sources || []" :key="source.source_id"
              ><details
                class="source-fields"
                :open="!sourcePreview.citation?.excerpt && !sourcePreview.images?.length"
              >
                <summary>Record details</summary>
                <div v-for="(value, field) in source.fields" :key="field">
                  <strong>{{ field.replaceAll('_', ' ') }}</strong>
                  <pre>{{ formattedField(value) }}</pre>
                </div>
                <StrixyAttachmentCoverage
                  v-if="source.attachment && typeof source.attachment === 'object'"
                  :outcomes="[{ source_id: source.source_id, ...source.attachment }]"
                  :source-labels="sourceLabels"
                />
                <p v-else-if="source.attachment">Attachment contents unexamined.</p>
              </details></template
            ></template
          ></v-card-text
        >
        <div class="strixy-dialog-actions">
          <v-btn variant="text" @click="closeSource">Close source</v-btn
          ><v-btn
            v-if="sourcePreview && !sharedSnapshot"
            color="primary"
            :disabled="!canChat || loading"
            @click="askAboutSource"
            >Ask about this</v-btn
          >
        </div></v-card
      ></v-dialog
    >

    <v-dialog v-model="sharingOpen" max-width="580" scrollable aria-label="Share this conversation"
      ><v-card
        class="strixy-dialog"
        rounded="xl"
        title="Share this conversation"
        subtitle="Give your case team a fixed copy."
      >
        <template #append>
          <v-btn
            icon="mdi-close"
            variant="text"
            aria-label="Close sharing"
            @click="sharingOpen = false"
          />
        </template>
        <v-card-text
          ><p class="dialog-note">
            Only authorized case readers can open a snapshot. Future private replies are excluded.
          </p>
          <p v-if="shareThroughMessage">
            Share through:
            {{ shareThroughMessage.role === 'assistant' ? 'Strixy’s answer' : 'Your question' }} ·
            {{ formatDate(shareThroughMessage.timestamp) }}
          </p>
          <v-btn
            v-if="shareThroughMessage"
            class="my-4"
            color="primary"
            :loading="sharing"
            @click="createShare(shareThroughMessage.id)"
            >Create snapshot</v-btn
          >
          <p v-if="shareError" class="dialog-note" role="status">{{ shareError }}</p>
          <h3 class="shared-heading">Shared snapshots</h3>
          <div v-for="share in shares" :key="share.id" class="shared-snapshot">
            <v-text-field
              :model-value="shareLink(share.id)"
              label="Snapshot link"
              readonly
              hide-details
            />
            <div>
              <span>{{ share.message_count }} messages · {{ formatDate(share.created_at) }}</span
              ><v-btn variant="text" size="small" @click="revokeShare(share.id)"
                >Revoke snapshot</v-btn
              >
            </div>
          </div>
          <p v-if="!shares.length" class="dialog-note">No snapshots have been shared.</p>
          <details class="sharing-details">
            <summary>How access works</summary>
            <p>
              Revocation removes access to a snapshot. It cannot retract information already read or
              delete independent follow-ups. A private follow-up keeps the original sources’ access
              restrictions.
            </p>
          </details></v-card-text
        ></v-card
      ></v-dialog
    >
    <ConfirmationDialog ref="confirmDialog" />
    <v-snackbar v-model="exportError" timeout="5000" location="top center"
      >Unable to export this conversation. Reopen it to check current access.</v-snackbar
    >
  </v-main>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useActiveCaseStore } from '@/stores/activeCase'
import { useStrixyChat } from '@/composables/useStrixyChat'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'
import StrixyAttachmentCoverage from '@/components/StrixyAttachmentCoverage.vue'
import StrixyMessage from '@/components/StrixyMessage.vue'
import { citationLocation, hasIncompleteReview, sourceLabel } from '@/utils/strixyDisplay'
import { formatDate } from '@/composables/dateUtils'
import { downloadBlob } from '@/utils/download'

const activeCase = useActiveCaseStore()
const route = useRoute()
const router = useRouter()
const {
  shares,
  sharedSnapshot,
  shareError,
  sharing,
  createShare,
  revokeShare,
  openShare,
  copyShare: copySharedConversation,
  latestRun,
  coverageLimits,
  visibleMessages,
  controlRun,
  sourcePreview,
  sourceError,
  openSource,
  authorizedExport,
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
  selectConversation: selectPrivateConversation,
  deleteConversation,
  operationError,
  refreshConversations,
} = useStrixyChat()
const initializing = ref(true)
const changingConversation = ref(false)
const historyOpen = ref(false)
const historyLoading = ref(false)
const historyQuery = ref('')
const sharingOpen = ref(false)
const shareThroughId = ref(null)
const reviewIndex = ref(null)
const exportError = ref(false)
const confirmDialog = ref(null)
const messageInput = ref(null)
const starterPrompts = [
  {
    title: 'Catch me up',
    detail: 'The essentials, in a minute',
    text: 'Give me a quick briefing on this case.',
    icon: 'mdi-text-box-outline',
  },
  {
    title: 'Find the gaps',
    detail: 'What we still need to know',
    text: 'What are the gaps in this case?',
    icon: 'mdi-magnify',
  },
  {
    title: 'Build a timeline',
    detail: 'Put the events in order',
    text: 'Build a timeline from the case records.',
    icon: 'mdi-timeline-clock-outline',
  },
]
const sourceLabels = computed(() =>
  Object.fromEntries(
    visibleMessages.value.flatMap((message) =>
      message.withheld
        ? []
        : [
            ...(message.citations || [])
              .filter((citation) => citation.title)
              .map((citation) => [citation.source_id, sourceLabel(citation)]),
            ...Object.entries(message.source_labels || {}).map(([id, label]) => [
              id,
              sourceLabel({ ...label, source_id: id }),
            ]),
          ],
    ),
  ),
)
const displayMessages = computed(() =>
  visibleMessages.value.map((message) => ({
    ...message,
    citations: (message.citations || []).map((citation) => ({
      ...citation,
      title:
        message.source_labels?.[citation.source_id]?.title ||
        citation.title ||
        sourceLabels.value[citation.source_id],
    })),
  })),
)
const reviewedMessage = computed(() =>
  reviewIndex.value === null
    ? null
    : displayMessages.value[reviewIndex.value]?.withheld
      ? null
      : displayMessages.value[reviewIndex.value],
)
const shareableMessages = computed(() =>
  displayMessages.value.filter((message) => !message.withheld && message.id),
)
const shareThroughMessage = computed(() =>
  shareableMessages.value.find((message) => message.id === shareThroughId.value),
)
const hasUserMessages = computed(() => messages.value.some((message) => message.role === 'user'))
const labelForSourcePreview = computed(() =>
  sourceLabel({
    ...sourcePreview.value?.citation,
    title:
      sourcePreview.value?.citation?.title ||
      sourceLabels.value[sourcePreview.value?.citation?.source_id],
  }),
)
const sourcePreviewTitle = computed(() =>
  sourcePreview.value ? labelForSourcePreview.value : 'Source unavailable',
)
const filteredConversations = computed(() =>
  conversations.value
    .map((conversation) => {
      const first =
        conversation.id === conversationId.value
          ? messages.value.find((message) => message.role === 'user')
          : null
      const title = first?.withheld
        ? 'Conversation unavailable'
        : first?.content?.trim().replace(/\s+/g, ' ').slice(0, 120) ||
          conversation.title ||
          'New conversation'
      return { ...conversation, title }
    })
    .filter((conversation) =>
      conversation.title.toLowerCase().includes((historyQuery.value || '').trim().toLowerCase()),
    ),
)
const progressLabel = computed(
  () =>
    ({
      locating_records: 'Locating records',
      examining_inputs: 'Reviewing case records',
      preparing_findings: 'Preparing findings',
    })[latestRun.value?.progress] || 'Strixy is thinking…',
)
const canContinue = computed(
  () =>
    !loading.value &&
    latestRun.value &&
    (latestRun.value.limit_code ||
      latestRun.value.status === 'cancelled' ||
      (hasIncompleteReview(latestRun.value.source_coverage) &&
        latestRun.value.status !== 'failed')),
)
const recoveryNotice = computed(() => {
  const run = latestRun.value
  if (!run || sharedSnapshot.value || loading.value) return ''
  if (run.error_code === 'sources_changed')
    return 'A source changed. Review the case again to use the current records.'
  if (run.status === 'cancelled') return 'Analysis cancelled. Saved partial findings are retained.'
  if (run.status === 'failed')
    return 'Strixy couldn’t finish this reply. Your question and any saved findings are still here.'
  if (canContinue.value)
    return 'The review is incomplete. Continue to examine more of the available material.'
  return ''
})
function formattedField(value) {
  try {
    return JSON.stringify(JSON.parse(value), null, 2)
  } catch {
    return value
  }
}
function composerKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    if (!initializing.value && !changingConversation.value) sendMessage()
  }
}
async function startPrompt(text) {
  if (!canChat.value || loading.value || initializing.value || changingConversation.value) return
  currentMessage.value = text
  await sendMessage()
}
function closeDialogs() {
  historyOpen.value = false
  sharingOpen.value = false
  reviewIndex.value = null
  shareThroughId.value = null
}
async function clearShareQuery() {
  if (route?.query.share) {
    const query = { ...route.query }
    delete query.share
    await router.replace({ query })
  }
}
async function selectConversation(id) {
  if (changingConversation.value) return
  changingConversation.value = true
  closeDialogs()
  try {
    await selectPrivateConversation(id)
    await clearShareQuery()
  } finally {
    changingConversation.value = false
  }
}
async function handleNewChat() {
  if (changingConversation.value) return
  changingConversation.value = true
  closeDialogs()
  try {
    await createConversation()
    if (conversationId.value) await clearShareQuery()
    await nextTick()
    messageInput.value?.focus()
  } finally {
    changingConversation.value = false
  }
}
async function copyShare() {
  await copySharedConversation()
  if (conversationId.value) await clearShareQuery()
}
async function openHistory() {
  historyLoading.value = true
  historyQuery.value = ''
  historyOpen.value = true
  await refreshConversations()
  historyLoading.value = false
}
function openSharing(id) {
  shareThroughId.value = id
  sharingOpen.value = true
}
function inspectReviewedSource(citation) {
  reviewIndex.value = null
  openSource(citation)
}
function closeSource() {
  sourcePreview.value = null
  sourceError.value = ''
}
function askAboutSource() {
  const source = sourcePreview.value?.citation
  if (!source) return
  currentMessage.value = `What does ${sourceLabel(source)} tell us?`
  closeSource()
  nextTick(() => messageInput.value?.focus())
}
async function handleDelete() {
  try {
    await confirmDialog.value.confirm({
      title: 'Delete conversation',
      message:
        'Remove this conversation, its replies, and all its shared snapshots from Owlculus? Independent follow-ups remain. This does not change the provider’s retention policies.',
      icon: 'mdi-delete',
      confirmText: 'Delete',
      confirmColor: 'error',
    })
  } catch {
    return
  }
  closeDialogs()
  await deleteConversation()
}
async function exportChat() {
  if (!hasUserMessages.value) return
  const saved = await authorizedExport()
  if (!saved) {
    exportError.value = true
    return
  }
  const payload = {
    title: 'Strixy Chat Export',
    case_id: saved.case_id,
    exportTime: new Date().toISOString(),
    messages: saved.messages.map((message) => ({
      role: message.role,
      content: message.content,
      timestamp: message.timestamp,
      citations: message.citations,
      coverage: message.coverage,
      withheld: message.withheld,
    })),
  }
  downloadBlob(
    { blob: new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }) },
    `strixy_chat_${Date.now()}.json`,
  )
}
const shareLink = (id) =>
  `${window.location.origin}/case/${activeCase.activeCaseId}/strixy?share=${encodeURIComponent(id)}`
async function openLinkedShare() {
  if (
    typeof route?.query.share === 'string' &&
    String(route.params.caseId) === String(activeCase.activeCaseId)
  ) {
    closeDialogs()
    await openShare(route.query.share)
  }
}
onMounted(async () => {
  try {
    await initializeChat()
    await openLinkedShare()
  } finally {
    initializing.value = false
  }
})
watch(() => route?.query.share, openLinkedShare)
watch(
  () => conversationId.value,
  () => {
    reviewIndex.value = null
    shareThroughId.value = null
  },
)
</script>

<style>
.strixy-page,
.strixy-dialog {
  --strixy-accent: #00585f;
  --strixy-text: #233b3e;
  --strixy-muted: #627578;
  --strixy-line: #dde5e4;
  --strixy-soft: #edf5f3;

  color: var(--strixy-text);
}

.v-theme--owlculusDark .strixy-page,
.v-theme--owlculusDark .strixy-dialog,
.strixy-dialog.v-theme--owlculusDark {
  --strixy-accent: #8ed6ce;
  --strixy-text: #e0eae8;
  --strixy-muted: #a6b7b3;
  --strixy-line: #384744;
  --strixy-soft: #233a36;
}

.strixy-dialog :where(h3, p) {
  margin: 0;
}

.strixy-dialog .v-card-subtitle {
  color: var(--strixy-muted);
}

.strixy-dialog :is(.v-card-title, .v-list-item-title) {
  white-space: normal;
  overflow-wrap: anywhere;
}

.strixy-dialog-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 18px 24px;
  border-top: 1px solid var(--strixy-line);
}

.strixy-page button:focus-visible,
.strixy-dialog button:focus-visible {
  outline: 2px solid var(--strixy-accent);
  outline-offset: 3px;
}
</style>
<style scoped>
.strixy-page {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
}

.strixy-page :where(h1, h2, p) {
  margin: 0;
}

.strixy-header {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  min-height: 88px;
  padding: 18px 30px;
  border-bottom: 1px solid var(--strixy-line);
}

.strixy-brand h1 {
  font-size: 19px;
  line-height: 1.4;
  font-weight: 600;
  letter-spacing: -0.5px;
}

.strixy-brand p {
  color: var(--strixy-muted);
  font-size: 10px;
  margin-top: 1px;
}

.strixy-brand :where(p) span {
  padding: 0 5px;
}

.strixy-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--strixy-muted);
}

.strixy-header-actions .v-btn {
  font-size: 12px;
  letter-spacing: 0;
  border-radius: 8px;
}

.strixy-layout {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: 820px;
  margin: 0 auto;
  padding: 0 34px 16px;
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 30px 3px 22px;
  scrollbar-width: thin;
  scroll-padding: 24px;
}

.strixy-empty .chat-messages {
  display: flex;
  align-items: center;
}

.strixy-welcome {
  width: 100%;
  padding: 22px 0;
}

.strixy-eyebrow {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1.3px;
  text-transform: uppercase;
  color: var(--strixy-muted);
}

.strixy-welcome h2 {
  font-size: clamp(25px, 3vw, 37px);
  letter-spacing: -1.2px;
  font-weight: 600;
  line-height: 1.2;
  margin: 12px 0 16px;
}

.strixy-welcome-copy {
  font-size: 15px;
  line-height: 1.8;
  color: var(--strixy-muted);
}

.strixy-starters {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 34px;
}

.strixy-starters button {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 20px 16px;
  border: 1px solid var(--strixy-line);
  border-radius: 12px;
  text-align: left;
  background: transparent;
  color: inherit;
  font-family: inherit;
  cursor: pointer;
}

.strixy-starters button:disabled {
  opacity: 0.5;
  cursor: default;
}

.strixy-starters button:hover:enabled {
  background: var(--strixy-soft);
  border-color: var(--strixy-accent);
}

.strixy-starters button > .v-icon:first-child {
  margin-bottom: 20px;
  color: var(--strixy-accent);
}

.strixy-starters strong {
  font-size: 14px;
  font-weight: 600;
}

.strixy-starters span {
  color: var(--strixy-muted);
  font-size: 11px;
  margin-top: 5px;
}

.starter-arrow {
  position: absolute;
  top: 20px;
  right: 14px;
  color: var(--strixy-muted);
}

.strixy-compose-area {
  flex-shrink: 0;
  padding-top: 12px;
  background: rgb(var(--v-theme-surface));
}

.strixy-composer {
  padding: 15px 16px 11px;
  border: 1px solid #9fb9b6;
  border-radius: 15px;
  background: rgb(var(--v-theme-surface));
  box-shadow: 0 3px 12px #173b3b06;
}

.strixy-composer:focus-within {
  outline: 2px solid var(--strixy-accent);
  outline-offset: 2px;
}

.strixy-composer textarea {
  display: block;
  width: 100%;
  min-height: 54px;
  max-height: 180px;
  border: 0;
  outline: 0;
  background: transparent;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.7;
  resize: vertical;
  color: var(--strixy-text);
}

.strixy-composer textarea::placeholder {
  color: var(--strixy-muted);
  opacity: 1;
}

.strixy-composer-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.strixy-compose-hint {
  flex: 1;
  text-align: right;
  font-size: 10px;
  color: var(--strixy-muted);
}

.strixy-composer-note {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
  padding-top: 12px;
  font-size: 10px;
  color: var(--strixy-muted);
}

.strixy-composer-note span {
  padding: 0 4px;
}

.strixy-notice {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
  padding: 12px 14px;
  background: var(--strixy-soft);
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.7;
}

.strixy-notice > div {
  flex: 1;
}

.strixy-notice > .v-btn {
  margin-left: auto;
  font-size: 11px;
}

.strixy-notice p {
  margin-top: 4px;
}

.run-notice {
  margin: 0;
}

.strixy-loading {
  display: flex;
  gap: 12px;
  align-items: center;
  color: var(--strixy-muted);
  font-size: 13px;
  padding: 20px 0;
}

.dialog-search {
  padding: 0 24px 16px;
}

.dialog-note {
  color: var(--strixy-muted);
  font-size: 13px;
  line-height: 1.8;
  margin: 12px 0;
}

.review-citation blockquote,
.source-excerpt {
  padding: 12px 16px;
  margin: 16px 0;
  border-left: 2px solid var(--strixy-accent);
  background: var(--strixy-soft);
  font-size: 13px;
  line-height: 1.9;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.review-citation-number {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: var(--strixy-accent);
  background: var(--strixy-soft);
  font-size: 12px;
}

.review-coverage {
  margin-top: 25px;
  font-size: 13px;
  line-height: 1.9;
}

.review-coverage h3 {
  font-size: 15px;
  margin-bottom: 10px;
}

.source-image {
  display: block;
  max-width: 100%;
  max-height: 65vh;
  object-fit: contain;
  margin: 15px auto;
}

.source-fields {
  margin-top: 18px;
  font-size: 13px;
}

.source-fields summary,
.sharing-details summary {
  cursor: pointer;
  padding: 10px 0;
}

.source-fields strong {
  display: block;
  margin: 12px 0 4px;
  text-transform: capitalize;
}

.source-fields pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 12px;
  line-height: 1.8;
}

.shared-heading {
  margin: 18px 0 10px;
  font-size: 15px;
}

.shared-snapshot {
  margin: 18px 0;
}

.shared-snapshot > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  color: var(--strixy-muted);
}

.sharing-details {
  font-size: 12px;
  color: var(--strixy-muted);
  margin-top: 20px;
}

.sharing-details p {
  line-height: 1.9;
}

@media (width <= 750px) {
  .strixy-header {
    padding: 17px 18px;
  }

  .strixy-header-actions {
    gap: 2px;
  }

  .strixy-header-actions .v-btn {
    min-width: 36px;
    padding: 0 9px;
  }

  .strixy-header-actions :deep(.v-btn__prepend) {
    margin: 0;
  }

  .strixy-header-actions :deep(.v-btn__content > span) {
    display: none;
  }
}

@media (width <= 600px) {
  .strixy-layout {
    padding: 0 18px 16px;
  }

  .strixy-welcome {
    padding: 20px 0 16px;
  }

  .strixy-welcome > .strixy-eyebrow {
    display: none;
  }

  .strixy-welcome h2 {
    margin: 0 0 12px;
    font-size: 25px;
  }

  .strixy-welcome-copy {
    font-size: 13px;
  }

  .strixy-starters {
    grid-template-columns: 1fr;
    gap: 8px;
    margin-top: 20px;
  }

  .strixy-starters button {
    display: grid;
    grid-template-columns: 26px 1fr;
    column-gap: 10px;
    align-items: center;
    padding: 12px 14px;
  }

  .strixy-starters button > .v-icon:first-child {
    margin: 0;
  }

  .strixy-starters span,
  .starter-arrow,
  .desktop-break {
    display: none;
  }
}

@media (width <= 450px) {
  .strixy-brand-role {
    display: none;
  }

  .strixy-brand p {
    font-size: 9px;
  }

  .strixy-compose-hint {
    visibility: hidden;
  }
}
</style>
