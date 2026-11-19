<template>
  <v-dialog v-model="open" max-width="560" scrollable aria-label="Your conversations"
    ><v-card
      class="strixy-dialog"
      rounded="xl"
      title="Your conversations"
      subtitle="Private to you, within this case."
    >
      <template #append>
        <v-btn
          icon="mdi-close"
          variant="text"
          aria-label="Close conversations"
          @click="open = false"
        />
      </template>
      <div class="dialog-search">
        <v-text-field
          v-model="query"
          label="Find a conversation"
          prepend-inner-icon="mdi-magnify"
          hide-details
          clearable
        />
      </div>
      <v-card-text
        ><div v-if="loading" class="strixy-loading">
          <v-progress-circular indeterminate size="20" />Loading conversations…
        </div>
        <template v-else
          ><v-list v-if="filteredConversations.length" class="pa-0">
            <v-list-item
              v-for="conversation in filteredConversations"
              :key="conversation.id"
              :title="conversation.title"
              :subtitle="formatDate(conversation.created_at)"
              prepend-icon="mdi-chat-outline"
              append-icon="mdi-chevron-right"
              lines="two"
              @click="emit('select', conversation.id)"
            />
          </v-list>
          <p v-if="!filteredConversations.length" class="dialog-note">
            {{
              conversations.length
                ? 'No matching conversations.'
                : 'Your conversations will appear here.'
            }}
          </p></template
        ></v-card-text
      >
      <div class="strixy-dialog-actions">
        <v-btn color="primary" prepend-icon="mdi-plus" :disabled="disabled" @click="emit('new')"
          >New conversation</v-btn
        >
      </div></v-card
    ></v-dialog
  >
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { formatDate } from '@/composables/dateUtils'

const props = defineProps({
  conversations: { type: Array, default: () => [] },
  messages: { type: Array, default: () => [] },
  conversationId: { type: [String, Number], default: null },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['select', 'new'])
const open = defineModel({ type: Boolean, default: false })
const query = ref('')

watch(open, (isOpen) => {
  if (isOpen) query.value = ''
})

const filteredConversations = computed(() =>
  props.conversations
    .map((conversation) => {
      const first =
        conversation.id === props.conversationId
          ? props.messages.find((message) => message.role === 'user')
          : null
      const title = first?.withheld
        ? 'Conversation unavailable'
        : first?.content?.trim().replace(/\s+/g, ' ').slice(0, 120) ||
          conversation.title ||
          'New conversation'
      return { ...conversation, title }
    })
    .filter((conversation) =>
      conversation.title.toLowerCase().includes((query.value || '').trim().toLowerCase()),
    ),
)
</script>

<style scoped>
.strixy-loading {
  display: flex;
  gap: 12px;
  align-items: center;
  color: var(--strixy-muted);
  font-size: 13px;
  padding: 20px 0;
}

.dialog-search {
  padding: 0 24px 16px;
}
</style>
