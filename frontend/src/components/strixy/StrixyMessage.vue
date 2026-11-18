<template>
  <article
    class="strixy-message"
    :class="message.role === 'user' ? 'user-message' : 'assistant-message'"
  >
    <div class="message-heading">
      <span>{{
        message.role === 'assistant' ? 'Strixy' : shared ? 'Conversation participant' : 'You'
      }}</span
      ><time v-if="message.timestamp" :datetime="message.timestamp">{{ time }}</time
      ><v-menu v-if="!message.withheld && !shared && message.id" location="bottom end"
        ><template #activator="{ props }"
          ><v-btn
            v-bind="props"
            icon="mdi-dots-horizontal"
            variant="text"
            size="x-small"
            :aria-label="`Actions for ${message.role === 'assistant' ? 'answer' : 'question'}`" /></template
        ><v-list
          ><v-list-item
            title="Share through here"
            prepend-icon="mdi-share-variant-outline"
            :disabled="sharing"
            @click="$emit('share', message.id)" /></v-list
      ></v-menu>
    </div>
    <p v-if="message.partial" class="message-notice">Partial findings · review is incomplete</p>
    <p v-if="message.withheld" class="message-notice" role="status">
      This answer is unavailable because a required source is unavailable or access changed.
    </p>
    <div v-else class="message-content" v-html="renderedContent" />
    <template v-if="!message.withheld && message.role === 'assistant'">
      <p v-if="hasIncompleteReview(message.coverage)" class="message-notice">
        Some records or attachments were not fully reviewed.
      </p>
      <p
        v-if="message.citations?.some((citation) => citation.source_status === 'changed')"
        class="message-notice"
      >
        Source changed since this answer.
      </p>
      <div v-if="message.citations?.length" class="message-citations" aria-label="Sources">
        <button
          v-for="(citation, index) in message.citations.slice(0, 3)"
          :key="`${citation.source_id}:${citation.field}:${index}`"
          :aria-label="`Open source ${index + 1}: ${sourceLabel(citation)}`"
          @click="$emit('source', citation)"
        >
          <span class="citation-number">{{ index + 1 }}</span
          ><span>{{ sourceLabel(citation) }}</span>
        </button>
      </div>
      <button
        v-if="message.coverage || message.citations?.length"
        class="review-button"
        @click="$emit('review')"
      >
        <v-icon icon="mdi-book-open-page-variant-outline" size="16" />{{
          message.citations?.length || 0
        }}
        {{ message.citations?.length === 1 ? 'reference' : 'references'
        }}<span v-if="message.coverage">
          · {{ message.coverage.counts?.read || 0 }}
          {{ message.coverage.counts?.read === 1 ? 'record' : 'records' }} reviewed</span
        ><span> · Review details</span><v-icon icon="mdi-chevron-right" size="15" />
      </button>
    </template>
  </article>
</template>
<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import { hasIncompleteReview, sourceLabel } from '@/utils/strixyDisplay'
const props = defineProps({
  message: { type: Object, required: true },
  shared: Boolean,
  sharing: Boolean,
})
defineEmits(['source', 'review', 'share'])
const markdown = new MarkdownIt({ html: false, linkify: false, typographer: true, breaks: true })
markdown.disable(['link', 'image', 'autolink'])
const renderedContent = computed(() => markdown.render(props.message.content || ''))
const time = computed(() =>
  new Date(props.message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
)
</script>
<style scoped>
.strixy-message {
  margin-bottom: 32px;
  overflow-wrap: anywhere;
}

.user-message {
  max-width: 90%;
  width: fit-content;
  margin-left: auto;
  padding: 12px 18px;
  border-radius: 15px 15px 4px;
  background: var(--strixy-soft);
}

.assistant-message {
  padding: 5px 0;
}

.message-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--strixy-muted);
  margin-bottom: 12px;
  font-size: 11px;
}

.message-heading > span {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--strixy-accent);
  font-weight: 600;
}

.message-heading time {
  margin-left: auto;
  white-space: nowrap;
}

.message-content {
  font-size: 14px;
  line-height: 1.85;
}

.message-content :deep(p) {
  margin: 0 0 14px;
}

.message-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-content :deep(h1),
.message-content :deep(h2) {
  font-size: 23px;
  font-weight: 600;
  line-height: 1.4;
  margin: 20px 0 12px;
}

.message-content :deep(h3),
.message-content :deep(h4) {
  font-size: 16px;
  line-height: 1.5;
  margin: 18px 0 8px;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 10px 0 18px;
  padding-left: 23px;
}

.message-content :deep(li) {
  margin-bottom: 8px;
}

.message-content :deep(blockquote) {
  margin: 20px 0;
  padding-left: 15px;
  border-left: 2px solid var(--strixy-accent);
}

.message-content :deep(pre) {
  padding: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  border-radius: 8px;
  background: var(--strixy-soft);
}

.message-content :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 16px 0;
}

.message-content :deep(th),
.message-content :deep(td) {
  padding: 8px;
  text-align: left;
  border: 1px solid var(--strixy-line);
}

.message-notice {
  font-size: 12px;
  line-height: 1.7;
  color: var(--strixy-muted);
  border-left: 2px solid var(--strixy-accent);
  padding-left: 10px;
  margin: 14px 0;
}

.message-citations {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 22px;
}

.message-citations button {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 8px 5px 4px;
  max-width: 100%;
  border: 1px solid var(--strixy-line);
  border-radius: 7px;
  background: none;
  color: var(--strixy-accent);
  font-size: 11px;
  text-align: left;
}

.message-citations button > span:last-child {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.citation-number {
  display: grid;
  place-items: center;
  min-width: 24px;
  height: 24px;
  background: var(--strixy-soft);
  border-radius: 5px;
  font-size: 10px;
}

.review-button {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 16px;
  padding: 6px 0;
  border: 0;
  background: none;
  color: var(--strixy-muted);
  font-size: 11px;
  text-align: left;
}
</style>
