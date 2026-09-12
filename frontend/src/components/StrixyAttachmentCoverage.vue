<template>
  <div v-for="outcome in outcomes" :key="outcome.source_id" class="mt-1">
    {{ outcome.source_id }}: {{ states[outcome.state] || 'Attachment unexamined' }}.
    <span v-if="outcome.units_read">{{ outcome.units_read }} content units prepared.</span>
    {{ reasons[outcome.reason] || '' }}
    <span v-if="outcome.text_truncated">Only part of the prepared text was supplied.</span>
    <span v-for="warning in outcome.warnings || []" :key="warning">
      {{ reasons[warning] || 'Some content could not be faithfully examined.' }}
    </span>
  </div>
</template>

<script setup>
defineProps({ outcomes: { type: Array, default: () => [] } })
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
