const kinds = {
  case: 'Case',
  entity: 'Entity',
  evidence: 'Evidence',
  plugin_result: 'Plugin result',
  hunt_result: 'Hunt result',
  hunt_step: 'Hunt step',
}

export function sourceLabel(source = {}) {
  if (source.title?.trim()) return source.title.trim()
  const [kind, id] = (source.source_id || '').split(':')
  return `${kinds[kind] || 'Record'}${id ? ` #${id}` : ''}`
}

export function citationLocation(citation) {
  const page = /^attachment:page:(\d+):/.exec(citation.field || '')
  if (page) return `Page ${page[1]}`
  const line = /^attachment:line:(\d+)$/.exec(citation.field || '')
  if (line) return `Line ${line[1]}`
  return (citation.field || 'Record').replaceAll('_', ' ').replaceAll(':', ' · ')
}

export function hasIncompleteReview(coverage) {
  return (
    coverage &&
    (coverage.complete === false ||
      (coverage.attachment_outcomes || []).some(
        (outcome) => outcome.state !== 'read' || outcome.text_truncated || outcome.warnings?.length,
      ))
  )
}
