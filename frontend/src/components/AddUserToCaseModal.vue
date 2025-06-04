<template>
  <v-dialog v-model="dialogVisible" max-width="500px" persistent>
    <v-card>
      <v-card-title>
        <span class="text-h5">Add User to Case</span>
      </v-card-title>
      <v-card-text>
        <div v-if="loading" class="flex justify-center mt-4">
          <v-progress-circular
            indeterminate
            :size="50"
            :width="8"
            color="primary"
          />
        </div>
        <v-alert v-else-if="error" type="error" class="mb-4">
          {{ error }}
        </v-alert>
        <v-form v-else>
          <v-select
            v-model="selectedUserId"
            :items="availableUsers"
            item-title="email"
            item-value="id"
            label="Select User"
            placeholder="Select a user"
            variant="outlined"
            density="comfortable"
          />
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="$emit('close')"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="handleAddUser"
          :disabled="!selectedUserId || loading"
        >
          Add User
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { userService } from '@/services/user';
import { caseService } from '@/services/case';
// Vuetify components are auto-imported

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

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
});

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
