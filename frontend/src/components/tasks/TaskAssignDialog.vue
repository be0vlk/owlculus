<template>
  <v-card>
    <v-card-title>Assign Task</v-card-title>
    <v-card-subtitle>{{ task.title }}</v-card-subtitle>
    <v-card-text>
      <v-select
        v-model="selectedUserId"
        :items="caseUsers"
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
      <v-btn color="primary" @click="emit('assign', selectedUserId)">
        {{ selectedUserId ? 'Assign' : 'Unassign' }}
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { caseService } from '@/services/case'

const props = defineProps({
  task: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['assign', 'cancel'])

const selectedUserId = ref(props.task.assigned_to_id)
const caseUsers = ref([])

onMounted(async () => {
  try {
    caseUsers.value = await caseService.getCaseUsers(props.task.case_id)
  } catch (error) {
    console.error('Failed to load data:', error)
  }
})
</script>
