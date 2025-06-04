<template>
  <v-dialog v-model="dialogVisible" max-width="800px" persistent>
    <v-card>
      <v-card-title>
        <span class="text-h5">Add New Entity</span>
      </v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" class="mb-4">
          {{ error }}
        </v-alert>
        <v-form @submit.prevent="handleSubmit">
              <div>
                <label for="entityType" class="block text-sm font-medium mb-1">Entity Type</label>
                <v-select
                  v-model="formData.entity_type"
                  :items="[
                    { value: 'person', title: 'Person' },
                    { value: 'company', title: 'Company' },
                    { value: 'domain', title: 'Domain' },
                    { value: 'ip_address', title: 'IP Address' }
                  ]"
                  item-title="title"
                  item-value="value"
                  variant="outlined"
                  density="comfortable"
                />
              </div>

              <div v-if="formData.entity_type === 'person'" class="space-y-4">
                <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label for="firstName" class="block text-sm font-medium mb-1">First Name</label>
                    <v-text-field id="firstName" v-model="formData.data.first_name" variant="outlined" density="compact" />
                  </div>
                  <div>
                    <label for="lastName" class="block text-sm font-medium mb-1">Last Name</label>
                    <v-text-field id="lastName" v-model="formData.data.last_name" variant="outlined" density="compact" />
                  </div>
                </div>
              </div>

              <div v-if="formData.entity_type === 'company'" class="space-y-4">
                <div>
                  <label for="companyName" class="block text-sm font-medium mb-1">Company Name</label>
                  <v-text-field id="companyName" v-model="formData.data.name" variant="outlined" density="compact" required />
                </div>
              </div>

              <div v-if="formData.entity_type === 'domain'" class="space-y-4">
                <div>
                  <label for="domain" class="block text-sm font-medium mb-1">Domain Name</label>
                  <v-text-field id="domain" v-model="formData.data.domain" placeholder="example.com" variant="outlined" density="compact" required />
                </div>
                <div>
                  <label for="domain_description" class="block text-sm font-medium mb-1">Description</label>
                  <v-textarea id="domain_description" v-model="formData.data.description" placeholder="Add any notes or context about this domain" variant="outlined" density="compact" rows="3" />
                </div>
              </div>

              <div v-if="formData.entity_type === 'ip_address'" class="space-y-4">
                <div>
                  <label for="ip_address" class="block text-sm font-medium mb-1">IP Address</label>
                  <v-text-field id="ip_address" v-model="formData.data.ip_address" placeholder="192.168.1.1" variant="outlined" density="compact" required />
                </div>
                <div>
                  <label for="ip_description" class="block text-sm font-medium mb-1">Description</label>
                  <v-textarea id="ip_description" v-model="formData.data.description" placeholder="Add any notes or context about this IP address" variant="outlined" density="compact" rows="3" />
                </div>
              </div>

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
          @click="handleSubmit"
          :disabled="creating"
          :loading="creating"
        >
          {{ creating ? 'Adding...' : 'Add Entity' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { watch, computed } from 'vue';
import { entityService } from '../services/entity';
import { useForm } from '../composables/useForm';
import { cleanFormData } from '../utils/cleanFormData';
// Vuetify components are auto-imported

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  caseId: { type: String, required: true },
});

const emit = defineEmits(['close', 'created']);

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
});

const initialFormData = {
  entity_type: '',
  data: {
    social_media: { x: '', linkedin: '', facebook: '', instagram: '', tiktok: '', reddit: '', other: '' },
    domains: [],
    ip_addresses: [],
    subdomains: [],
  },
};

const { formData, error, creating, handleSubmit } = useForm(initialFormData, async (formData) => {
  const submitData = {
    entity_type: formData.entity_type,
    data: cleanFormData({ ...formData.data }),
  };

  const response = await entityService.createEntity(props.caseId, submitData);
  emit('created', response);
  emit('close');
});

watch(() => formData.entity_type, (newType) => {
  const baseSocialMedia = formData.data.social_media;
  formData.data = {
    social_media: baseSocialMedia,
    domains: [],
    ip_addresses: [],
    subdomains: [],
  };

  if (newType === 'person') {
    Object.assign(formData.data, {
      first_name: '',
      last_name: ''
    });
  } else if (newType === 'company') {
    Object.assign(formData.data, {
      name: ''
    });
  }
});
</script>