<template>
  <v-dialog
    :model-value="isOpen"
    :aria-label="client ? 'Edit Client' : 'New Client'"
    max-width="500px"
    persistent
    @update:model-value="!$event && $emit('close')"
  >
    <v-card>
      <v-card-title>
        <span class="text-headline-small">{{ client ? 'Edit Client' : 'New Client' }}</span>
      </v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
        <v-form :id="formId" ref="formRef" :disabled="isSubmitting" @submit.prevent="submit">
          <v-text-field
            v-model="form.name"
            label="Name"
            required
            :rules="[(v) => !!v?.trim() || 'Name is required']"
            autofocus
            variant="outlined"
            density="comfortable"
          />

          <v-text-field
            v-model="form.email"
            label="Email"
            :rules="[(v) => !v || /.+@.+\..+/.test(v) || 'Email must be valid']"
            type="email"
            variant="outlined"
            density="comfortable"
          />

          <v-text-field
            v-model="form.phone"
            label="Phone"
            type="tel"
            variant="outlined"
            density="comfortable"
          />

          <v-textarea
            v-model="form.address"
            label="Address"
            rows="3"
            variant="outlined"
            density="comfortable"
          />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="isSubmitting" variant="text" @click="$emit('close')"> Cancel </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          type="submit"
          :form="formId"
          :disabled="isSubmitting"
          :loading="isSubmitting"
        >
          {{ client ? 'Update Client' : 'Create Client' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, useId, watch } from 'vue'
import { clientService } from '../services/client'

// Without a client the modal creates one.
const props = defineProps({
  isOpen: { type: Boolean, required: true },
  client: { type: Object, default: null },
})

const emit = defineEmits(['close', 'saved'])

const formId = useId()
const formRef = ref(null)
const isSubmitting = ref(false)
const error = ref('')
const form = ref({})

watch(
  () => props.isOpen,
  (open) => {
    if (!open) return
    const { name, email, phone, address } = props.client ?? {}
    form.value = {
      name: name || '',
      email: email || '',
      phone: phone || '',
      address: address || '',
    }
    error.value = ''
  },
  { immediate: true },
)

const submit = async () => {
  if (isSubmitting.value) return
  const { valid } = await formRef.value.validate()
  if (!valid || isSubmitting.value) return
  error.value = ''
  isSubmitting.value = true
  const data = { ...form.value, email: form.value.email || null }
  try {
    const saved = props.client
      ? await clientService.updateClient(props.client.id, data)
      : await clientService.createClient(data)
    emit('saved', saved)
    emit('close')
  } catch (err) {
    error.value = `Failed to ${props.client ? 'update' : 'create'} client. Please try again.`
    console.error('Error saving client:', err)
  } finally {
    isSubmitting.value = false
  }
}
</script>
