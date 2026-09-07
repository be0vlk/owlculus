/** Assemble authorized continuation parts for cards and exports without mutating retained events. */
export function assembleCorrelationResults(result) {
  const events = result ? (Array.isArray(result) ? result : [result]) : []
  const groups = new Map()
  const others = []
  for (const [index, event] of events.entries()) {
    const part = event.data
    if (event.type !== 'data' || !Array.isArray(part?.matches)) {
      others.push(event)
      continue
    }
    const key = part.group_id || `legacy:${index}`
    if (!groups.has(key)) groups.set(key, { ...part, source_fields: [], matches: new Map() })
    const group = groups.get(key)
    group.source_fields = mergeFields(group.source_fields, part.source_fields)
    for (const match of part.matches) {
      const identity = `${match.case_id}:${match.entity_id}`
      const previous = group.matches.get(identity)
      group.matches.set(identity, {
        ...match,
        ...(match.fields || previous?.fields
          ? { fields: mergeFields(previous?.fields, match.fields) }
          : {}),
      })
    }
  }
  const assembled = [...groups.values()].map((group) => ({
    ...group,
    matches: [...group.matches.values()].sort(
      (a, b) =>
        rank(a, group) - rank(b, group) || a.case_id - b.case_id || a.entity_id - b.entity_id,
    ),
  }))
  assembled.sort(
    (a, b) =>
      groupRank(a) - groupRank(b) ||
      a.entity_id - b.entity_id ||
      compare(a.match_type, b.match_type) ||
      compare(a.normalized_value || '', b.normalized_value || ''),
  )
  return [...assembled.map((data) => ({ type: 'data', data })), ...others]
}

const compare = (a, b) => (a < b ? -1 : a > b ? 1 : 0)
const rank = (match, group) =>
  match.signal_rank ?? (['email', 'phone', 'vin'].includes(group.match_type) ? 0 : 1)
const groupRank = (group) =>
  group.matches.reduce((best, match) => Math.min(best, rank(match, group)), 2)
const mergeFields = (first = [], second = []) => [
  ...new Map(
    [...first, ...second].map((field) => [JSON.stringify([field.field, field.value]), field]),
  ).values(),
]
