<template>
  <v-dialog v-model="dialog" max-width="500px" aria-label="Rename evidence" :persistent="loading">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon :icon="item?.is_folder ? 'mdi-folder-edit' : 'mdi-file-edit'" class="mr-2"></v-icon>
        Rename {{ item?.is_folder ? 'Folder' : 'File' }}
      </v-card-title>

      <v-card-text>
        <v-form ref="form" v-model="valid" validate-on="lazy" @submit.prevent="rename">
          <v-text-field
            autofocus
            v-model="newName"
            label="Name"
            :rules="nameRules"
            required
            :prepend-inner-icon="item?.is_folder ? 'mdi-folder' : 'mdi-file'"
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
        @cancel="dialog = false"
        @submit="rename"
      />
    </v-card>
  </v-dialog>
</template>

<script>
export const nameRules = [
  (v) => !!v?.trim() || 'Name is required',
  (v) => v.length <= 255 || 'Name must be less than 255 characters',
  (v) =>
    /^[a-zA-Z0-9._\s-]+$/.test(v) ||
    'Name can only contain letters, numbers, spaces, dots, underscores, and hyphens',
]
</script>

<script setup>
import { getErrorMessage } from '@/utils/errorMessage'
import { useDialogFocusRestore } from '@/composables/useDialogFocusRestore'
import { ref, watch } from 'vue'
import { evidenceService } from '../services/evidence'
import ModalActions from './ModalActions.vue'

const props = defineProps({
  item: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['renamed'])

// Reactive data
const form = ref()
const valid = ref(false)
const loading = ref(false)
const error = ref('')
const newName = ref('')

const dialog = defineModel({ type: Boolean, default: false })

// Methods
const rename = async () => {
  if (loading.value) return
  const { valid: isValid } = await form.value.validate()
  if (!isValid) return

  loading.value = true
  error.value = ''

  try {
    const update = props.item.is_folder ? 'updateFolder' : 'updateEvidence'
    emit('renamed', await evidenceService[update](props.item.id, { title: newName.value.trim() }))
    dialog.value = false
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to rename item')
  } finally {
    loading.value = false
  }
}

watch([dialog, () => props.item], () => {
  if (dialog.value && props.item) newName.value = props.item.title
})
useDialogFocusRestore(() => dialog.value)
</script>
