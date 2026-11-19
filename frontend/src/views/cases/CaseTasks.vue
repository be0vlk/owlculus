<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-4">
      <div>
        <div class="text-title-large">Tasks</div>
        <div class="text-body-medium text-medium-emphasis">Manage tasks for this case</div>
      </div>
      <v-btn v-if="canCreateTasks" color="primary" @click="showCreateDialog = true">
        <v-icon start>mdi-plus</v-icon>
        New Task
      </v-btn>
    </div>

    <TaskTable :loading="loading" :tasks="tasks" />

    <v-dialog aria-label="Create Task" v-model="showCreateDialog" max-width="600">
      <TaskForm :saving="loading" @cancel="showCreateDialog = false" @save="handleCreateTask" />
    </v-dialog>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
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

const showCreateDialog = ref(false)

const loading = computed(() => taskStore.loading)
const tasks = computed(() => taskStore.tasks.filter((t) => t.case_id === props.caseId))

async function loadTasks() {
  await taskStore.loadTasks()
}

async function handleCreateTask(taskData) {
  if (loading.value) return
  await taskStore.createTask(taskData)
  showCreateDialog.value = false
  await loadTasks()
}

watch(() => props.caseId, loadTasks, { immediate: true })
</script>
