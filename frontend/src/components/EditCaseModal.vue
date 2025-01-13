<template>
  <div v-if="show" class="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
    <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
      <!-- Background overlay -->
      <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" @click="$emit('close')"></div>

      <!-- Modal panel -->
      <div class="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
        <div class="sm:flex sm:items-start">
          <div class="mt-3 text-center sm:mt-0 sm:text-left w-full">
            <h3 class="text-lg leading-6 font-medium text-gray-900 dark:text-white" id="modal-title">
              Edit Case
            </h3>
            
            <!-- Error Message -->
            <div v-if="error" class="mt-2 p-2 bg-red-100 text-red-700 rounded-md text-sm">
              {{ error }}
            </div>

            <!-- Edit Form -->
            <form @submit.prevent="handleSubmit" class="mt-4 space-y-4">
              <div>
                <BaseInput
                  label="Title"
                  id="title"
                  v-model="formData.title"
                  required
                />
              </div>

              <div>
                <BaseSelect
                  label="Status"
                  id="status"
                  v-model="formData.status"
                  :options="[
                    { value: 'Open', label: 'Open' },
                    { value: 'Closed', label: 'Closed' }
                  ]"
                  required
                />
              </div>

              <!-- Modal footer -->
              <div class="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                <button
                  type="submit"
                  :disabled="updating"
                  class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-cyan-600 text-base font-medium text-white hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50"
                >
                  {{ updating ? 'Saving...' : 'Save Changes' }}
                </button>
                <button
                  type="button"
                  @click="$emit('close')"
                  class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:mt-0 sm:w-auto sm:text-sm dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../services/api'
import BaseInput from './BaseInput.vue'
import BaseSelect from './BaseSelect.vue'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  caseData: {
    type: Object,
    required: true,
    default: () => ({
      title: '',
      status: ''
    })
  }
})

const emit = defineEmits(['close', 'update'])

const formData = ref({
  title: '',
  status: ''
})
const updating = ref(false)
const error = ref(null)

// Use watch instead of onMounted to handle updates to caseData
watch(() => props.caseData, (newValue) => {
  if (newValue) {
    formData.value = {
      title: newValue.title || '',
      status: newValue.status || ''
    }
  }
}, { immediate: true })

const handleSubmit = async () => {
  if (!formData.value) return
  
  updating.value = true
  error.value = null
  
  try {
    const response = await api.put(`/api/cases/${props.caseData.id}`, {
      title: formData.value.title,
      status: formData.value.status
    })
    emit('update', response.data)
    emit('close')
  } catch (err) {
    error.value = err.response?.data?.message || 'Failed to update case'
  } finally {
    updating.value = false
  }
}
</script>
