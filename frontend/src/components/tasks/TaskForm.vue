<template>
  <v-card>
    <v-card-title>{{ isEdit ? 'Edit Task' : 'Create Task' }}</v-card-title>
    <v-card-text>
      <v-form ref="form" v-model="valid">
        <v-select
          v-model="formData.case_id"
          :disabled="isEdit || !!caseId"
          :items="cases"
          :rules="[(v) => !!v || 'Case is required']"
          item-title="title"
          item-value="id"
          label="Case"
        />

        <v-text-field
          v-model="formData.title"
          :rules="[(v) => !!v || 'Title is required']"
          label="Title"
        />

        <v-textarea
          v-model="formData.description"
          :rules="[(v) => !!v || 'Description is required']"
          label="Description"
          rows="3"
        />

        <v-select
          v-if="!isEdit"
          v-model="formData.template_id"
          :items="templates"
          clearable
          item-title="display_name"
          item-value="id"
          label="Template (Optional)"
        />

        <v-select v-model="formData.priority" :items="priorityOptions" label="Priority" />

        <v-select
          v-model="formData.assigned_to_id"
          :items="users"
          clearable
          item-title="username"
          item-value="id"
          label="Assign To"
        />

        <v-text-field v-model="formData.due_date" clearable label="Due Date" type="date" />
      </v-form>
    </v-card-text>
    <v-card-actions>
      <v-spacer />
      <v-btn @click="$emit('cancel')">Cancel</v-btn>
      <v-btn :disabled="!valid" :loading="loading" color="primary" @click="save">
        {{ isEdit ? 'Update' : 'Create' }}
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { caseService } from '@/services/case'
import { userService } from '@/services/user'
import { TASK_PRIORITY, TASK_PRIORITY_LABELS } from '@/constants/tasks'

const props = defineProps({
  task: {
    type: Object,
    default: null,
  },
  caseId: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['save', 'cancel'])

const taskStore = useTaskStore()

const form = ref(null)
const valid = ref(false)
const loading = ref(false)
const cases = ref([])
const users = ref([])

const isEdit = computed(() => !!props.task)

const formData = ref({
  case_id: props.caseId || props.task?.case_id || null,
  title: props.task?.title || '',
  description: props.task?.description || '',
  template_id: null,
  priority: props.task?.priority || TASK_PRIORITY.MEDIUM,
  assigned_to_id: props.task?.assigned_to_id || null,
  due_date: props.task?.due_date ? props.task.due_date.split('T')[0] : null,
})

const templates = computed(() => taskStore.templates)

const priorityOptions = computed(() =>
  Object.entries(TASK_PRIORITY_LABELS).map(([value, title]) => ({ title, value })),
)

async function save() {
  if (!form.value.validate()) return

  loading.value = true
  try {
    // Format date if present
    const data = { ...formData.value }
    if (data.due_date) {
      data.due_date = new Date(data.due_date).toISOString()
    }

    emit('save', data)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // Load required data
  try {
    const [casesData, usersData] = await Promise.all([
      caseService.getCases(),
      userService.getUsers(),
      taskStore.loadTemplates(),
    ])
    cases.value = casesData
    users.value = usersData
  } catch (error) {
    console.error('Failed to load data:', error)
  }
})
</script>
