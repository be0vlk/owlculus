import { expect, it } from 'vitest'
import {
  assembleCorrelationResults,
  correlationRows,
  entityLabel,
} from '@/utils/correlationResults'

const group = (data, matches) => ({
  type: 'data',
  data: {
    case_id: 1,
    entity_id: 10,
    entity_type: 'person',
    entity_name: 'Ada',
    match_type: 'email',
    normalized_value: 'ada@example.org',
    matched_value: 'Ada@Example.org',
    source_fields: [{ field: 'email', value: 'Ada@Example.org' }],
    ...data,
    matches,
  },
})

const related = {
  case_id: 2,
  case_number: 'B-2',
  case_title: 'Related',
  entity_id: 20,
  entity_type: 'company',
  entity_name: 'Engines',
  fields: [{ field: 'email', value: 'ada@example.org' }],
  signal: 'Exact email match',
  signal_rank: 0,
}

const rows = (...events) => correlationRows(assembleCorrelationResults(events))

it('yields one row per match carrying source group and related entity details', () => {
  const [row] = rows(group({}, [related]), { type: 'complete', data: {} })
  expect(row).toEqual({
    key: '[10,"email","ada@example.org",2,20]',
    sourceEntityId: 10,
    sourceCaseId: 1,
    sourceLabel: 'Ada',
    sourceType: 'person',
    matchType: 'email',
    sharedValue: 'Ada@Example.org',
    sourceFields: [{ field: 'email', value: 'Ada@Example.org' }],
    entityId: 20,
    caseId: 2,
    caseNumber: 'B-2',
    caseTitle: 'Related',
    relatedLabel: 'Engines',
    relatedType: 'company',
    fields: [{ field: 'email', value: 'ada@example.org' }],
    foundIn: undefined,
    signal: 'Exact email match',
    strength: 0,
  })
})

it('keeps one source entity matching by several types as separate rows with distinct keys', () => {
  const result = rows(
    group({}, [related, { ...related, entity_id: 21 }]),
    group({ match_type: 'domain', normalized_value: 'example.org', matched_value: undefined }, [
      { ...related, signal_rank: 1 },
    ]),
  )
  expect(result).toHaveLength(3)
  expect(new Set(result.map((row) => row.key)).size).toBe(3)
  expect(new Set(result.map((row) => row.sourceEntityId))).toEqual(new Set([10]))
})

it('takes strength from signal_rank and falls back for legacy results', () => {
  const legacy = { case_id: 2, entity_id: 30 }
  const strengths = (type, match) =>
    rows(group({ match_type: type }, [match])).map((row) => row.strength)
  expect(strengths('email', { ...legacy, signal_rank: 1 })).toEqual([1])
  expect(strengths('email', legacy)).toEqual([0])
  expect(strengths('employer', legacy)).toEqual([1])
  expect(
    strengths('domain', { ...legacy, signal: 'Low signal: common email provider overlap' }),
  ).toEqual([2])
})

it('labels entities by name, then person name, then type and id', () => {
  expect(entityLabel({ entity_name: ' Ada ', entity_id: 1 })).toBe('Ada')
  expect(entityLabel({ entity_name: '', person_name: 'Charles', entity_id: 1 })).toBe('Charles')
  expect(entityLabel({ entity_type: 'vehicle', entity_id: 10 })).toBe('vehicle #10')
  expect(entityLabel({ entity_id: 10 })).toBe('Entity #10')
  const [row] = rows(group({ entity_name: '' }, [{ case_id: 2, entity_id: 20 }]))
  expect([row.sourceLabel, row.relatedLabel]).toEqual(['person #10', 'Entity #20'])
  expect(row.relatedType).toBe('person')
})

it('falls back to the normalized value, then the source label, for the shared value', () => {
  const shared = (data) =>
    rows(group({ matched_value: undefined, ...data }, [related]))[0].sharedValue
  expect(shared({ domain: 'example.org' })).toBe('example.org')
  expect(shared({ normalized_value: 'n' })).toBe('n')
  expect(shared({ normalized_value: undefined })).toBe('Ada')
})
