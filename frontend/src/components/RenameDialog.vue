<template>
  <v-dialog v-model="dialog" max-width="500px" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon :icon="item?.is_folder ? 'mdi-folder-edit' : 'mdi-file-edit'" class="mr-2"></v-icon>
        Rename {{ item?.is_folder ? 'Folder' : 'File' }}
      </v-card-title>

      <v-card-text>
        <v-form ref="form" v-model="valid" lazy-validation>
          <v-text-field
            v-model="newName"
            label="Name"
            :rules="nameRules"
            required
            variant="outlined"
            density="comfortable"
            :prepend-inner-icon="item?.is_folder ? 'mdi-folder' : 'mdi-file'"
            @keyup.enter="rename"
          ></v-text-field>

          <v-alert v-if="error" class="mb-0" type="error" variant="tonal">
            {{ error }}
          </v-alert>
        </v-form>
      </v-card-text>

      <modal-actions
        submit-text="Rename"
        submit-icon="mdi-rename-box"
        :submit-disabled="!valid || !newName.trim() || newName === item?.title"
        :loading="loading"
        @cancel="cancel"
        @submit="rename"
      />
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { evidenceService } from '../services/evidence'
import ModalActions from './ModalActions.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  item: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue', 'renamed'])

// Reactive data
const form = ref()
const valid = ref(false)
const loading = ref(false)
const error = ref('')
const newName = ref('')

// Computed
const dialog = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

// Validation rules
const nameRules = [
  (v) => !!v || 'Name is required',
  (v) => (v && v.length >= 1) || 'Name must be at least 1 character',
  (v) => (v && v.length <= 255) || 'Name must be less than 255 characters',
  (v) =>
    /^[a-zA-Z0-9._\s-]+$/.test(v) ||
    'Name can only contain letters, numbers, spaces, dots, underscores, and hyphens',
]

// Methods
const rename = async () => {
  if (!form.value.validate()) {
    return
  }

  loading.value = true
  error.value = ''

  try {
    let updatedItem

    if (props.item.is_folder) {
      updatedItem = await evidenceService.updateFolder(props.item.id, {
        title: newName.value.trim(),
      })
    } else {
      updatedItem = await evidenceService.updateEvidence(props.item.id, {
        title: newName.value.trim(),
      })
    }

    emit('renamed', updatedItem)
    dialog.value = false
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to rename item'
  } finally {
    loading.value = false
  }
}

const cancel = () => {
  dialog.value = false
}

// Watch for dialog open to set initial name
watch(dialog, (newVal) => {
  if (newVal && props.item) {
    newName.value = props.item.title
  }
})

// Watch for item changes
watch(
  () => props.item,
  (newItem) => {
    if (newItem) {
      newName.value = newItem.title
    }
  },
)
</script>
