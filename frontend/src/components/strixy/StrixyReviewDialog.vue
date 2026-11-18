<template>
  <v-dialog
    :model-value="!!message"
    max-width="650"
    scrollable
    aria-label="Behind this answer"
    @update:model-value="!$event && emit('close')"
    ><v-card
      v-if="message"
      class="strixy-dialog"
      rounded="xl"
      title="Behind this answer"
      :subtitle="`${message.citations?.length || 0} source references`"
    >
      <template #append>
        <v-btn
          icon="mdi-close"
          variant="text"
          aria-label="Close review details"
          @click="emit('close')"
        />
      </template>
      <v-card-text>
        <div
          v-for="(citation, index) in message.citations || []"
          :key="`${citation.source_id}:${citation.field}:${index}`"
          class="review-citation"
        >
          <v-list-item
            :title="sourceLabel(citation)"
            :subtitle="`${citationLocation(citation)} · Inspected ${formatDate(citation.inspected_at)}`"
            append-icon="mdi-chevron-right"
            lines="two"
            class="px-0"
            @click="emit('inspect', citation)"
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
        <section v-if="message.coverage" class="review-coverage">
          <h3>What was reviewed</h3>
          <p>
            {{ message.coverage.counts?.read || 0 }} records read,
            {{ message.coverage.counts?.partly_read || 0 }} partly read,
            {{ message.coverage.counts?.unexamined || 0 }} unexamined<span
              v-if="message.coverage.counts?.unavailable"
              >, {{ message.coverage.counts.unavailable }} unavailable</span
            >.
          </p>
          <p v-if="!message.coverage.complete">
            <strong>Incomplete coverage.</strong> {{ coverageLimits(message.coverage) }}
          </p>
          <p v-if="!message.coverage.enumeration_complete">
            The record limit was reached; more material may exist.
          </p>
          <StrixyAttachmentCoverage
            v-if="message.coverage.attachment_outcomes"
            :outcomes="message.coverage.attachment_outcomes"
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
</template>

<script setup>
import StrixyAttachmentCoverage from '@/components/strixy/StrixyAttachmentCoverage.vue'
import { citationLocation, sourceLabel } from '@/utils/strixyDisplay'
import { formatDate } from '@/composables/dateUtils'

defineProps({
  message: { type: Object, default: null },
  sourceLabels: { type: Object, default: () => ({}) },
  coverageLimits: { type: Function, required: true },
})
const emit = defineEmits(['close', 'inspect'])
</script>

<style scoped>
.review-citation blockquote {
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
</style>
