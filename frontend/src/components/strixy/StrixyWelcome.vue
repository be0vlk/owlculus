<template>
  <div class="strixy-welcome">
    <h2>Where should we start?</h2>
    <p class="strixy-welcome-copy">
      Ask a question. I’ll use your case records<br class="desktop-break" />
      and show you the sources.
    </p>
    <div class="strixy-starters">
      <button
        v-for="prompt in starterPrompts"
        :key="prompt.title"
        :disabled="disabled"
        @click="emit('start', prompt.text)"
      >
        <v-icon :icon="prompt.icon" size="22" /><strong>{{ prompt.title }}</strong
        ><span>{{ prompt.detail }}</span
        ><v-icon icon="mdi-arrow-up-right" size="16" class="starter-arrow" />
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({ disabled: { type: Boolean, default: false } })
const emit = defineEmits(['start'])

const starterPrompts = [
  {
    title: 'Catch me up',
    detail: 'The essentials, in a minute',
    text: 'Give me a quick briefing on this case.',
    icon: 'mdi-text-box-outline',
  },
  {
    title: 'Find the gaps',
    detail: 'What we still need to know',
    text: 'What are the gaps in this case?',
    icon: 'mdi-magnify',
  },
  {
    title: 'Build a timeline',
    detail: 'Put the events in order',
    text: 'Build a timeline from the case records.',
    icon: 'mdi-timeline-clock-outline',
  },
]
</script>

<style scoped>
.strixy-welcome {
  width: 100%;
  padding: 22px 0;
}

.strixy-welcome :where(h2, p) {
  margin: 0;
}

.strixy-welcome h2 {
  font-size: clamp(25px, 3vw, 37px);
  font-weight: 600;
  line-height: 1.2;
  margin: 0 0 16px;
}

.strixy-welcome-copy {
  font-size: 15px;
  line-height: 1.8;
  color: var(--strixy-muted);
}

.strixy-starters {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 34px;
}

.strixy-starters button {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 20px 16px;
  border: 1px solid var(--strixy-line);
  border-radius: 12px;
  text-align: left;
  background: transparent;
  color: inherit;
  font-family: inherit;
  cursor: pointer;
}

.strixy-starters button:disabled {
  opacity: 0.5;
  cursor: default;
}

.strixy-starters button:hover:enabled {
  background: var(--strixy-soft);
  border-color: var(--strixy-accent);
}

.strixy-starters button > .v-icon:first-child {
  margin-bottom: 20px;
  color: var(--strixy-accent);
}

.strixy-starters strong {
  font-size: 14px;
  font-weight: 600;
}

.strixy-starters span {
  color: var(--strixy-muted);
  font-size: 12px;
  margin-top: 5px;
}

.starter-arrow {
  position: absolute;
  top: 20px;
  right: 14px;
  color: var(--strixy-muted);
}

@media (width <= 600px) {
  .strixy-welcome {
    padding: 20px 0 16px;
  }

  .strixy-welcome h2 {
    margin: 0 0 12px;
    font-size: 25px;
  }

  .strixy-welcome-copy {
    font-size: 13px;
  }

  .strixy-starters {
    grid-template-columns: 1fr;
    gap: 8px;
    margin-top: 20px;
  }

  .strixy-starters button {
    display: grid;
    grid-template-columns: 26px 1fr;
    column-gap: 10px;
    align-items: center;
    padding: 12px 14px;
  }

  .strixy-starters button > .v-icon:first-child {
    margin: 0;
  }

  .strixy-starters span,
  .starter-arrow,
  .desktop-break {
    display: none;
  }
}
</style>
