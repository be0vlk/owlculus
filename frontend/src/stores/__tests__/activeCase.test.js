import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { caseService } from '../../services/case'
import { useActiveCaseStore, ACTIVE_CASE_STORAGE_KEY } from '../activeCase'

vi.mock('../../services/case', () => ({ caseService: { getCases: vi.fn() } }))
const older = {
  id: 1,
  case_number: 'OLD',
  title: 'Older',
  status: 'Closed',
  created_at: '2025-01-01',
}
const newer = {
  id: 2,
  case_number: 'NEW',
  title: 'Newer',
  status: 'Open',
  created_at: '2026-01-01',
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.restoreAllMocks()
  caseService.getCases.mockResolvedValue([older, newer])
})

describe('active case', () => {
  it('validates URL precedence over persistence, including Closed cases', async () => {
    localStorage.setItem(ACTIVE_CASE_STORAGE_KEY, '2')
    const store = useActiveCaseStore()
    await store.initialize('1')
    expect(store.activeCase).toEqual(older)
    expect(store.activeCaseId).toBe(1)
    expect(localStorage.getItem(ACTIVE_CASE_STORAGE_KEY)).toBe('1')
    expect(store.ready).toBe(true)
  })
})

it('restores a valid preference and otherwise picks newest with a stable id tie-breaker', async () => {
  caseService.getCases.mockResolvedValue([older, { ...newer, id: 3 }, newer])
  const store = useActiveCaseStore()
  await store.initialize()
  expect(store.activeCaseId).toBe(2)
  localStorage.setItem(ACTIVE_CASE_STORAGE_KEY, '1')
  store.reset()
  await store.initialize()
  expect(store.activeCaseId).toBe(1)
})

it('notifies and falls back to newest for an invalid URL even with a valid preference', async () => {
  localStorage.setItem(ACTIVE_CASE_STORAGE_KEY, '1')
  const store = useActiveCaseStore()
  await store.initialize('999')
  expect(store.activeCaseId).toBe(2)
  expect(store.notification).toContain('unavailable')
})

it('blocks requests during resolution, tolerates storage failures, and exposes an empty state', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  let finish
  caseService.getCases.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const store = useActiveCaseStore()
  const pending = store.initialize()
  expect(store.loading).toBe(true)
  expect(store.activeCaseId).toBeNull()
  finish([older])
  await pending
  expect(store.activeCaseId).toBe(1)
  expect(await store.select(null)).toBe(false)
  expect(store.activeCaseId).toBe(1)
  caseService.getCases.mockResolvedValue([])
  await store.refresh()
  expect(store.activeCaseId).toBeNull()
  expect(store.ready).toBe(true)
  expect(store.notification).toContain('No accessible cases remain')
})

it('keeps lifecycle changes selected but recovers after removal', async () => {
  const store = useActiveCaseStore()
  await store.initialize('2')
  caseService.getCases.mockResolvedValue([older, { ...newer, status: 'Closed' }])
  await store.refresh()
  expect(store.activeCase.status).toBe('Closed')
  expect(store.notification).toBe('')
  caseService.getCases.mockResolvedValue([older])
  await store.refresh()
  expect(store.activeCaseId).toBe(1)
  expect(localStorage.getItem(ACTIVE_CASE_STORAGE_KEY)).toBe('1')
  expect(store.notification).toContain('unavailable')
})

it('ignores an in-flight response from a logged-out session', async () => {
  let finish
  caseService.getCases.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const store = useActiveCaseStore()
  const pending = store.initialize('1')
  store.reset()
  finish([older])
  await pending
  expect(store.activeCaseId).toBeNull()
  expect(store.accessibleCases).toEqual([])
})

it('blocks stale context after a failed refresh and supports retry', async () => {
  const store = useActiveCaseStore()
  await store.initialize('1')
  caseService.getCases.mockRejectedValueOnce(new Error('offline'))
  await store.refresh()
  expect(store.activeCaseId).toBeNull()
  expect(store.error).toContain('retry')
  await store.refresh()
  expect(store.activeCaseId).toBe(1)
})

it('validates cases beyond the first API page', async () => {
  caseService.getCases.mockImplementation(async ({ skip }) =>
    skip === 0
      ? Array.from({ length: 100 }, (_, index) => ({ ...older, id: index + 10 }))
      : [newer],
  )
  const store = useActiveCaseStore()
  await store.initialize('2')
  expect(store.accessibleCases).toHaveLength(101)
  expect(store.activeCaseId).toBe(2)
})

it('keeps validated context available during ordinary refresh but blocks known access failures', async () => {
  const store = useActiveCaseStore()
  await store.initialize('1')
  let finish
  caseService.getCases.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const refresh = store.refresh()
  expect(store.activeCaseId).toBe(1)
  expect(store.refreshing).toBe(true)
  expect(await store.select(2)).toBe(false)
  finish([older, newer])
  await refresh
  caseService.getCases.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve
    }),
  )
  const recovery = store.recoverUnavailable(1)
  expect(store.activeCaseId).toBeNull()
  finish([older, newer])
  await recovery
  expect(store.activeCaseId).toBe(2)
})
