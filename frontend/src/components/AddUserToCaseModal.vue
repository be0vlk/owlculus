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
              Add User to Case
            </h3>

            <div v-if="loading" class="flex justify-center mt-4">
              <LoadingSpinner size="medium" />
            </div>
            <div v-else-if="error" class="mt-2 p-2 bg-red-100 text-red-700 rounded-md text-sm">
              {{ error }}
            </div>
            <div v-else class="mt-4 space-y-4">
              <div class="flex flex-col">
                <BaseSelect
                  label="Select User"
                  id="user"
                  v-model="selectedUserId"
                  :options="[
                    { value: '', label: 'Select a user' },
                    ...availableUsers.map(user => ({
                      value: user.id,
                      label: user.email
                    }))
                  ]"
                />
              </div>
            </div>

            <!-- Modal footer -->
            <div class="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
              <button
                type="button"
                :disabled="!selectedUserId || loading"
                class="ml-3 inline-flex justify-center px-4 py-2 text-sm font-medium text-white bg-cyan-600 border border-transparent rounded-md hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed"
                @click="handleAddUser"
              >
                Add User
              </button>
              <button
                type="button"
                class="mt-3 sm:mt-0 inline-flex justify-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
                @click="$emit('close')"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { userService } from '@/services/user';
import { caseService } from '@/services/case';
import LoadingSpinner from './LoadingSpinner.vue';
import BaseSelect from './BaseSelect.vue';

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  caseId: {
    type: Number,
    required: true
  }
});

const emit = defineEmits(['close', 'userAdded']);

const loading = ref(false);
const error = ref(null);
const selectedUserId = ref('');
const availableUsers = ref([]);

const loadUsers = async () => {
  try {
    loading.value = true;
    error.value = null;
    availableUsers.value = await userService.getUsers();
  } catch (err) {
    error.value = err.message || 'Failed to load users';
  } finally {
    loading.value = false;
  }
};

const handleAddUser = async () => {
  if (!selectedUserId.value) return;
  
  try {
    loading.value = true;
    error.value = null;
    await caseService.addUserToCase(props.caseId, selectedUserId.value);
    emit('userAdded');
    emit('close');
  } catch (err) {
    error.value = err.message || 'Failed to add user to case';
  } finally {
    loading.value = false;
  }
};

watch(() => props.show, (newValue) => {
  if (newValue) {
    loadUsers();
  } else {
    // Clear selection when modal is closed
    selectedUserId.value = '';
  }
});
</script>
