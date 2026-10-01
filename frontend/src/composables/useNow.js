import { onScopeDispose, ref, watch } from 'vue'

// One shared clock for live durations; it ticks only while some caller is active.
const now = ref(Date.now())
let timer
let users = 0

export function useNow(active = () => true) {
  let counted = false
  const count = (on) => {
    if (on === counted) return
    counted = on
    if (on && users++ === 0) {
      now.value = Date.now()
      timer = setInterval(() => (now.value = Date.now()), 1000)
    } else if (!on && --users === 0) clearInterval(timer)
  }
  watch(() => !!active(), count, { immediate: true })
  onScopeDispose(() => count(false))
  return now
}
