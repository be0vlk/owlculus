<template>
  <v-dialog v-model="open" max-width="580" scrollable aria-label="Share this conversation"
    ><v-card
      class="strixy-dialog"
      rounded="xl"
      title="Share this conversation"
      subtitle="Give your case team a fixed copy."
    >
      <template #append>
        <v-btn icon="mdi-close" variant="text" aria-label="Close sharing" @click="open = false" />
      </template>
      <v-card-text
        ><p class="dialog-note">
          Only authorized case readers can open a snapshot. Future private replies are excluded.
        </p>
        <p v-if="throughMessage">
          Share through:
          {{ throughMessage.role === 'assistant' ? 'Strixy’s answer' : 'Your question' }} ·
          {{ formatDate(throughMessage.timestamp) }}
        </p>
        <v-btn
          v-if="throughMessage"
          class="my-4"
          color="primary"
          :loading="sharing"
          @click="emit('create', throughMessage.id)"
          >Create snapshot</v-btn
        >
        <p v-if="error" class="dialog-note" role="status">{{ error }}</p>
        <h3 class="shared-heading">Shared snapshots</h3>
        <div v-for="share in shares" :key="share.id" class="shared-snapshot">
          <v-text-field
            :model-value="shareLink(share.id)"
            label="Snapshot link"
            readonly
            hide-details
          />
          <div>
            <span>{{ share.message_count }} messages · {{ formatDate(share.created_at) }}</span
            ><v-btn variant="text" size="small" @click="emit('revoke', share.id)"
              >Revoke snapshot</v-btn
            >
          </div>
        </div>
        <p v-if="!shares.length" class="dialog-note">No snapshots have been shared.</p>
        <details class="sharing-details">
          <summary>How access works</summary>
          <p>
            Revocation removes access to a snapshot. It cannot retract information already read or
            delete independent follow-ups. A private follow-up keeps the original sources’ access
            restrictions.
          </p>
        </details></v-card-text
      ></v-card
    ></v-dialog
  >
</template>

<script setup>
import { formatDate } from '@/composables/dateUtils'

const props = defineProps({
  throughMessage: { type: Object, default: null },
  shares: { type: Array, default: () => [] },
  sharing: { type: Boolean, default: false },
  error: { type: String, default: '' },
  caseId: { type: [String, Number], default: null },
})
const emit = defineEmits(['create', 'revoke'])
const open = defineModel({ type: Boolean, default: false })

const shareLink = (id) =>
  `${window.location.origin}/case/${props.caseId}/strixy?share=${encodeURIComponent(id)}`
</script>

<style scoped>
.shared-heading {
  margin: 18px 0 10px;
  font-size: 15px;
}

.shared-snapshot {
  margin: 18px 0;
}

.shared-snapshot > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  color: var(--strixy-muted);
}

.sharing-details {
  font-size: 12px;
  color: var(--strixy-muted);
  margin-top: 20px;
}

.sharing-details p {
  line-height: 1.9;
}
</style>
