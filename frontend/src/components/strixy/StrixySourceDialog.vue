<template>
  <v-dialog
    :model-value="!!preview || !!error"
    max-width="720"
    scrollable
    :aria-label="title"
    @update:model-value="emit('close')"
    ><v-card class="strixy-dialog" rounded="xl" :title="title" subtitle="Source preview">
      <template #append>
        <v-btn
          icon="mdi-close"
          variant="text"
          aria-label="Close source preview"
          @click="emit('close')"
        />
      </template>
      <v-card-text
        ><p v-if="error" role="status">{{ error }}</p>
        <template v-else-if="preview"
          ><p v-if="preview.citation?.source_status === 'changed'" class="dialog-note">
            Current file shown. This source changed since the historical answer.
          </p>
          <p class="dialog-note">{{ citationLocation(preview.citation || {}) }}</p>
          <blockquote v-if="preview.citation?.excerpt" class="source-excerpt">
            {{ preview.citation.excerpt }}
          </blockquote>
          <img
            v-for="image in preview.images || []"
            :key="image.field"
            :src="'data:image/png;base64,' + image.data"
            :alt="label + ' · ' + citationLocation(image)"
            class="source-image"
          /><template v-for="source in preview.sources || []" :key="source.source_id"
            ><details
              class="source-fields"
              :open="!preview.citation?.excerpt && !preview.images?.length"
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
        <v-btn variant="text" @click="emit('close')">Close source</v-btn
        ><v-btn v-if="preview && !readonly" color="primary" :disabled="!canAsk" @click="emit('ask')"
          >Ask about this</v-btn
        >
      </div></v-card
    ></v-dialog
  >
</template>

<script setup>
import { computed } from 'vue'
import StrixyAttachmentCoverage from '@/components/strixy/StrixyAttachmentCoverage.vue'
import { citationLocation, sourceLabel } from '@/utils/strixyDisplay'

const props = defineProps({
  preview: { type: Object, default: null },
  error: { type: String, default: '' },
  sourceLabels: { type: Object, default: () => ({}) },
  canAsk: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'ask'])

const label = computed(() =>
  sourceLabel({
    ...props.preview?.citation,
    title: props.preview?.citation?.title || props.sourceLabels[props.preview?.citation?.source_id],
  }),
)
const title = computed(() => (props.preview ? label.value : 'Source unavailable'))

function formattedField(value) {
  try {
    return JSON.stringify(JSON.parse(value), null, 2)
  } catch {
    return value
  }
}
</script>

<style scoped>
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
</style>
