<!-- THROWAWAY shared UI switcher; available only in the prototype dev server. -->
<template>
  <aside v-if="isDev" class="prototype-controls" aria-label="Prototype comparison controls">
    <section v-if="showState" class="prototype-state">
      <strong>{{ current.description }}</strong>
      <p>
        Option A selected, with alphabetized tabs and a shared Plugins &amp; Hunts tab. Fictional
        data; actions stay in memory.
      </p>
      <pre>{{
        JSON.stringify(
          {
            ...(current.key === 'original'
              ? { mode: 'Read-only baseline; returning to A/B/C resets preview edits' }
              : state),
            variant: current.key,
            tab: route.query.tab || 'entities',
          },
          null,
          2,
        )
      }}</pre>
    </section>
    <div class="prototype-bar">
      <span class="prototype-marker">PROTOTYPE</span>
      <v-btn
        icon="mdi-chevron-left"
        variant="text"
        size="small"
        aria-label="Previous variant"
        @click="cycle(-1)"
      />
      <v-menu location="top">
        <template #activator="{ props }">
          <button v-bind="props" class="prototype-label">
            {{ current.key === 'original' ? '0' : current.key }} · {{ current.name }}
            <v-icon size="16">mdi-chevron-down</v-icon>
          </button>
        </template>
        <v-list aria-label="Layout variants">
          <v-list-item
            v-for="variant in variants"
            :key="variant.key"
            :title="`${variant.key === 'original' ? '0' : variant.key} · ${variant.name}`"
            :active="current.key === variant.key"
            @click="select(variant.key)"
          />
        </v-list>
      </v-menu>
      <v-btn
        icon="mdi-chevron-right"
        variant="text"
        size="small"
        aria-label="Next variant"
        @click="cycle(1)"
      />
      <v-btn
        icon="mdi-information-outline"
        variant="text"
        size="small"
        aria-label="Prototype state and design intent"
        :aria-expanded="showState"
        @click="showState = !showState"
      />
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
defineProps({ state: { type: Object, default: () => ({}) } })
const isDev = import.meta.env.DEV
const route = useRoute()
const router = useRouter()
const showState = ref(false)
const variants = [
  {
    key: 'A',
    name: 'Open workspace',
    description:
      'A: A flat, full-width working surface. Compact identity; tabs separated from the content by a single rule.',
  },
  {
    key: 'B',
    name: 'Case file',
    description:
      'B: A framed document with attached tabs. Identity has its own margin; the working content sits inside one clear surface.',
  },
  {
    key: 'C',
    name: 'Workspace rail',
    description:
      'C: Labeled vertical workspace tabs beside the content. Deliberately explores a departure from the spec’s horizontal tabs; costs some table width.',
  },
  {
    key: 'original',
    name: 'Current design',
    description:
      '0: The current case dashboard, with the same sample case. Baseline controls are read-only; backend writes are blocked.',
  },
]
const current = computed(
  () => variants.find((item) => item.key === route.query.variant) || variants[0],
)
function select(key) {
  router.replace({ query: { ...route.query, variant: key } })
}
function cycle(direction) {
  select(
    variants[(variants.indexOf(current.value) + direction + variants.length) % variants.length].key,
  )
}
function onKey(event) {
  if (
    event.target.closest(
      'input, textarea, select, [contenteditable], [role="tablist"], [role="dialog"], [role="menu"]',
    ) ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey ||
    event.shiftKey
  )
    return
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault()
    cycle(event.key === 'ArrowLeft' ? -1 : 1)
  }
}
watch(
  current,
  (value) =>
    console.info('[Case workspace prototype]', {
      variant: value.key,
      intent: value.description,
      tab: route.query.tab || 'entities',
    }),
  { immediate: true },
)
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
:global(.vue-devtools__anchor) {
  display: none !important;
}

.prototype-controls {
  position: fixed;
  z-index: 2200;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
  max-width: calc(100vw - 20px);
  color: #fff;
}

.prototype-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border: 1px solid #506364;
  border-radius: 40px;
  background: #183336;
  box-shadow: 0 8px 28px #0003;
  white-space: nowrap;
}

.prototype-marker {
  margin: 0 10px;
  color: #aed1cd;
  font-size: 10px;
  letter-spacing: 1.6px;
  font-weight: 700;
}

.prototype-label {
  border: 0;
  background: transparent;
  cursor: pointer;
  padding: 7px 3px;
  font-size: 13px;
  color: #fff;
}

.prototype-state {
  margin-bottom: 12px;
  border: 1px solid #506364;
  border-radius: 14px;
  padding: 18px;
  background: #183336;
  font-size: 13px;
  max-height: 52vh;
  overflow: auto;
  width: 470px;
  max-width: calc(100vw - 20px);
}

.prototype-state p {
  margin: 8px 0;
  color: #c8dbd9;
}

.prototype-state pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 11px;
}

.prototype-label:focus-visible {
  outline: 2px solid white;
  outline-offset: 2px;
}

@media (width <= 600px) {
  .prototype-marker {
    display: none;
  }

  .prototype-bar {
    gap: 0;
    padding: 4px;
  }

  .prototype-controls {
    bottom: 10px;
  }
}
</style>
