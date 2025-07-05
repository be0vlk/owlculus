<template>
  <v-card>
    <v-card-title>Assign Task</v-card-title>
    <v-card-subtitle>{{ task.title }}</v-card-subtitle>
    <v-card-text>
      <v-select
        v-model="selectedUserId"
        :items="assignableUsers"
        clearable
        hint="Leave empty to unassign"
        item-title="username"
        item-value="id"
        label="Assign To"
        persistent-hint
      />
    </v-card-text>
    <v-card-actions>
      <v-spacer />
      <v-btn @click="$emit('cancel')">Cancel</v-btn>
      <v-btn :loading="loading" color="primary" @click="assign">
        {{ selectedUserId ? 'Assign' : 'Unassign' }}
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { userService } from '@/services/user'
import { caseService } from '@/services/case'

const props = defineProps({
  task: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['assign', 'cancel'])

const loading = ref(false)
const selectedUserId = ref(props.task.assigned_to_id)
const caseData = ref(null)
const users = ref([])

// Only show users who have access to the case
const assignableUsers = computed(() => {
  if (!caseData.value) return []

  // Filter users who are assigned to this case
  return users.value.filter((user) =>
    caseData.value.users?.some((cu) => cu.id === user.id)
  )
})

async function assign() {
  loading.value = true
  try {
    emit('assign', selectedUserId.value)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    // Load case and user data
    const [caseResult, usersResult] = await Promise.all([
      caseService.getCase(props.task.case_id),
      userService.getUsers()
    ])
    caseData.value = caseResult
    users.value = usersResult
  } catch (error) {
    console.error('Failed to load data:', error)
  }
})
</script>
