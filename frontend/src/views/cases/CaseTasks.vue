<template>
  <div>
    <!-- Header -->
    <div class="d-flex align-center justify-space-between mb-4">
      <div>
        <div class="text-h6">Tasks</div>
        <div class="text-body-2 text-medium-emphasis">Manage tasks for this case</div>
      </div>
      <v-btn v-if="canCreateTasks" color="primary" @click="showCreateDialog = true">
        <v-icon start>mdi-plus</v-icon>
        New Task
      </v-btn>
    </div>

    <!-- Tasks Table -->
    <TaskTable :loading="loading" :tasks="tasks" />

    <!-- Create Task Dialog -->
    <v-dialog v-model="showCreateDialog" max-width="600">
      <TaskForm :case-id="caseId" @cancel="showCreateDialog = false" @save="handleCreateTask" />
    </v-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { useTaskTable } from '@/composables/useTaskTable'
import TaskForm from '@/components/tasks/TaskForm.vue'
import TaskTable from '@/components/tasks/TaskTable.vue'

const props = defineProps({
  caseId: {
    type: Number,
    required: true,
  },
})

const taskStore = useTaskStore()
const { canCreateTasks } = useTaskTable()

// Data
const showCreateDialog = ref(false)

// Computed
const loading = computed(() => taskStore.loading)
const tasks = computed(() => taskStore.tasks.filter((t) => t.case_id === props.caseId))

// Methods
async function loadTasks() {
  await taskStore.loadTasks({ case_id: props.caseId })
}

async function handleCreateTask(taskData) {
  await taskStore.createTask(taskData)
  showCreateDialog.value = false
  await loadTasks()
}

// Watch for case ID changes
watch(
  () => props.caseId,
  () => {
    loadTasks()
  },
)

// Lifecycle
onMounted(async () => {
  await loadTasks()
})
</script>
