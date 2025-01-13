<template>
  <TransitionRoot appear :show="isOpen" as="template">
    <Dialog as="div" @close="closeModal" class="relative z-10">
      <TransitionChild
        as="template"
        enter="duration-300 ease-out"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="duration-200 ease-in"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="fixed inset-0 bg-black bg-opacity-25" />
      </TransitionChild>

      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4 text-center">
          <TransitionChild
            as="template"
            enter="duration-300 ease-out"
            enter-from="opacity-0 scale-95"
            enter-to="opacity-100 scale-100"
            leave="duration-200 ease-in"
            leave-from="opacity-100 scale-100"
            leave-to="opacity-0 scale-95"
          >
            <DialogPanel class="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
              <DialogTitle as="h3" class="text-lg font-medium leading-6 text-gray-900">
                New Case
              </DialogTitle>

              <form @submit.prevent="handleSubmit" class="mt-4 space-y-4">
                <div>
                  <label for="title" class="block text-sm font-medium text-gray-700">Title</label>
                  <input
                    type="text"
                    id="title"
                    v-model="form.title"
                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-500 focus:ring-cyan-500 text-gray-900"
                    required
                  />
                </div>

                <div>
                  <label for="client" class="block text-sm font-medium text-gray-700">Client</label>
                  <select
                    id="client"
                    v-model="form.client_id"
                    class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-cyan-500 focus:ring-cyan-500 text-gray-900"
                    required
                  >
                    <option value="">Select a client</option>
                    <option v-for="client in clients" :key="client.id" :value="client.id">
                      {{ client.name }}
                    </option>
                  </select>
                </div>

                <div class="mt-6 flex justify-end space-x-3">
                  <button
                    type="button"
                    @click="closeModal"
                    class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    class="rounded-md border border-transparent bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2"
                    :disabled="isSubmitting"
                  >
                    {{ isSubmitting ? 'Creating...' : 'Create Case' }}
                  </button>
                </div>
              </form>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'
import { clientService } from '../services/client'
import { caseService } from '../services/case'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['close', 'created'])

const authStore = useAuthStore()
const clients = ref([])
const isSubmitting = ref(false)
const form = reactive({
  title: '',
  client_id: '',
  status: 'Open'
})

const loadClients = async () => {
  // Only load clients if user is admin
  if (!authStore.requiresAdmin()) {
    return;
  }
  
  try {
    clients.value = await clientService.getClients()
  } catch (error) {
    console.error('Error loading clients:', error)
  }
}

const closeModal = () => {
  // Reset form
  form.title = ''
  form.client_id = ''
  form.status = 'Open'
  emit('close')
}

const handleSubmit = async () => {
  try {
    isSubmitting.value = true
    const newCase = await caseService.createCase(form)
    emit('created', newCase)
    closeModal()
  } catch (error) {
    console.error('Error creating case:', error)
    // TODO: Add proper error handling UI
  } finally {
    isSubmitting.value = false
  }
}

onMounted(loadClients)
</script>