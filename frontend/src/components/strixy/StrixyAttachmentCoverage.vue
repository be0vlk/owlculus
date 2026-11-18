<template>
  <div v-for="outcome in outcomes" :key="outcome.source_id" class="mt-1">
    {{ sourceLabels[outcome.source_id] || sourceLabel(outcome) }}:
    {{ states[outcome.state] || 'Attachment unexamined' }}.
    <span v-if="outcome.units_read">{{ outcome.units_read }} content units prepared.</span>
    <div v-for="page in outcome.pages || []" :key="page.unit">
      Page/image {{ page.unit }}: {{ states[page.state] || 'Unexamined' }}.
      {{ reasons[page.reason] || '' }}
    </div>
    <div v-if="outcome.unexamined_from">
      Pages {{ outcome.unexamined_from }}–{{ outcome.total_units }} unexamined in this run.
    </div>
    {{ reasons[outcome.reason] || '' }}
    <span v-if="outcome.text_truncated">Only part of the prepared text was supplied.</span>
    <span v-for="warning in outcome.warnings || []" :key="warning">
      {{ reasons[warning] || 'Some content could not be faithfully examined.' }}
    </span>
  </div>
</template>

<script setup>
import { sourceLabel } from '@/utils/strixyDisplay'
defineProps({
  outcomes: { type: Array, default: () => [] },
  sourceLabels: { type: Object, default: () => ({}) },
})
const states = {
  read: 'Attachment examined',
  partly_read: 'Attachment partly examined',
  unavailable: 'Attachment unavailable',
  unexamined: 'Attachment unexamined',
}
const reasons = {
  attachment_unit_limit: 'Attachment unit limit reached. Continue analysis to examine more.',
  attachment_size_limit: 'File exceeds the analysis size limit.',
  attachment_expansion_limit: 'Expanded document exceeds the processing limit.',
  attachment_time_limit: 'Attachment preparation time limit reached.',
  attachment_processing_limit: 'Attachment processing limit reached.',
  visual_input_limit: 'Visual input budget reached. Continue analysis to examine more.',
  visual_pixel_limit: 'Page or image exceeds the pixel processing limit.',
  visual_resolution_reduced: 'Resolution was reduced; small text or details may be unreadable.',
  unreadable_page: 'This page could not be rendered faithfully.',
  vision_unavailable: 'The configured model does not support visual analysis.',
  animated_image_unsupported: 'Animated images are not supported for analysis.',
  interactive_content_unexamined: 'Interactive form content was not examined.',
  encrypted_file: 'File is encrypted. An authorized reader can upload an unlocked copy.',
  unreadable_file: 'File is damaged or could not be read faithfully.',
  file_unavailable: 'Stored file is unavailable.',
  source_changed: 'File changed during preparation. Request a new analysis.',
  unsupported_format: 'This attachment format is not supported for analysis.',
  converter_unavailable:
    'Document converter is unavailable. Ask an administrator to check the installation.',
  visual_or_embedded_content_unexamined: 'Visual or embedded content was not examined.',
  inherited_slide_content_unexamined: 'Inherited slide layout and master content was not examined.',
  external_content_unexamined: 'Linked external content was not retrieved.',
  legacy_layout_and_visuals_unexamined: 'Legacy document layout and visuals were not examined.',
  formulas_not_evaluated: 'Formulas were not evaluated; cached values may be stale.',
  display_formatting_unexamined: 'Stored cell values were read without display formatting.',
}
</script>
