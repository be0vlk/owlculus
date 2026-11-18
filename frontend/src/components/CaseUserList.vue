<template>
  <v-list v-if="members.length" density="compact" class="mb-4">
    <v-list-item v-for="user in members" :key="user.id" class="px-0">
      <template #prepend>
        <v-avatar color="grey-lighten-1" size="32">
          <v-icon>mdi-account</v-icon>
        </v-avatar>
      </template>

      <v-list-item-title>
        {{ user.email }}
        <v-icon v-if="user.is_lead" class="ml-1" color="primary" size="x-small">mdi-star</v-icon>
        <v-chip
          v-if="user.role === 'Analyst'"
          class="ml-2"
          color="grey"
          size="x-small"
          variant="tonal"
        >
          {{ user.role }}
        </v-chip>
      </v-list-item-title>
      <v-list-item-subtitle>{{ userDisplayName(user) }}</v-list-item-subtitle>

      <template #append>
        <div class="d-flex align-center ga-1">
          <v-tooltip :text="leadTooltip(user)" location="top">
            <template #activator="{ props: tooltip }">
              <v-btn
                v-bind="tooltip"
                :aria-label="`${leadTooltip(user)} for ${user.email}`"
                :color="user.is_lead ? 'primary' : 'default'"
                :icon="user.is_lead ? 'mdi-star' : 'mdi-star-outline'"
                :loading="busyUserId === user.id"
                :disabled="user.role === 'Analyst' && !user.is_lead"
                size="small"
                variant="text"
                @click="$emit('toggle-lead', user)"
              />
            </template>
          </v-tooltip>

          <v-tooltip :text="`Remove from ${removeTarget}`" location="top">
            <template #activator="{ props: tooltip }">
              <v-btn
                v-bind="tooltip"
                :aria-label="`Remove ${user.email} from ${removeTarget}`"
                :loading="busyUserId === user.id"
                color="error"
                icon="mdi-account-remove"
                size="small"
                variant="text"
                @click="$emit('remove', user)"
              />
            </template>
          </v-tooltip>
        </div>
      </template>
    </v-list-item>
  </v-list>
  <slot v-else name="empty" />

  <v-row class="align-center">
    <v-col cols="12" md="6">
      <v-select
        v-model="userToAdd"
        :autofocus="autofocus"
        :items="availableUsers"
        clearable
        item-title="displayText"
        item-value="id"
        label="Select User"
        placeholder="Choose a user to add"
      />
    </v-col>
    <v-col cols="12" md="3">
      <v-checkbox
        v-model="isLead"
        density="comfortable"
        hide-details
        label="Set as Lead"
        :disabled="selectedIsAnalyst"
      />
    </v-col>
    <v-col cols="12" md="3">
      <v-btn
        :disabled="!userToAdd"
        :loading="adding"
        block
        color="primary"
        prepend-icon="mdi-account-plus"
        variant="tonal"
        @click="add"
      >
        Add User
      </v-btn>
    </v-col>
  </v-row>

  <v-alert
    v-if="!availableUsers.length"
    class="mt-4"
    icon="mdi-information"
    type="info"
    variant="tonal"
  >
    <v-alert-title>No Users Available</v-alert-title>
    All users are already assigned
  </v-alert>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { isStrixy, userDisplayName } from '@/utils/userDisplay'

const props = defineProps({
  users: { type: Array, required: true },
  allUsers: { type: Array, required: true },
  removeTarget: { type: String, default: 'selection' },
  adding: Boolean,
  busyUserId: { type: Number, default: null },
  autofocus: Boolean,
})

const emit = defineEmits(['add', 'toggle-lead', 'remove'])

const userToAdd = ref(null)
const isLead = ref(false)

const members = computed(() => props.users.filter((user) => !isStrixy(user)))

const availableUsers = computed(() =>
  props.allUsers
    .filter((user) => !isStrixy(user) && !props.users.some(({ id }) => id === user.id))
    .map((user) => ({
      ...user,
      displayText: `${user.email} - ${userDisplayName(user)} (${user.role})`,
    })),
)

const selectedIsAnalyst = computed(
  () => props.allUsers.find((user) => user.id === userToAdd.value)?.role === 'Analyst',
)
watch(selectedIsAnalyst, (analyst) => {
  if (analyst) isLead.value = false
})

const leadTooltip = (user) => {
  if (user.role === 'Analyst' && !user.is_lead) return 'Analysts cannot be set as leads'
  return user.is_lead ? 'Remove as Lead' : 'Set as Lead'
}

const add = () => {
  emit('add', userToAdd.value, isLead.value)
  userToAdd.value = null
  isLead.value = false
}
</script>
