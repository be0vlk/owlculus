import { afterEach, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { calculateDuration } from '../huntDisplayUtils'
import { useNow } from '@/composables/useNow'

afterEach(() => vi.useRealTimers())

it('reads zone-less hunt timestamps as UTC', () => {
  vi.useFakeTimers({ now: new Date('2026-01-01T12:01:05Z') })
  expect(calculateDuration('2026-01-01T12:00:00')).toBe('1m 5s')
  expect(calculateDuration('2026-01-01T12:00:00Z', '2026-01-01T14:30:00+00:00')).toBe('2h 30m')
  expect(calculateDuration('2026-01-01T12:02:00Z')).toBe('0s')
})

it('runs one shared ticker only while an active caller exists', async () => {
  vi.useFakeTimers()
  const running = ref(false)
  const a = effectScope()
  const b = effectScope()
  a.run(() => useNow(() => running.value))
  b.run(() => useNow())
  expect(vi.getTimerCount()).toBe(1)
  running.value = true
  await nextTick()
  expect(vi.getTimerCount()).toBe(1)
  b.stop()
  expect(vi.getTimerCount()).toBe(1)
  running.value = false
  await nextTick()
  expect(vi.getTimerCount()).toBe(0)
  a.stop()
  expect(vi.getTimerCount()).toBe(0)
})
