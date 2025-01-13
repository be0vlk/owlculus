<template>
  <div v-if="show" class="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
    <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
      <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" @click="$emit('close')"></div>

      <div class="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full sm:p-6">
        <div class="sm:flex sm:items-start">
          <div class="mt-3 text-center sm:mt-0 sm:text-left w-full">
            <h3 class="text-lg leading-6 font-medium text-gray-900 dark:text-white" id="modal-title">
              Add New Entity
            </h3>

            <div v-if="error" class="mt-2 p-2 bg-red-100 text-red-700 rounded-md text-sm">
              {{ error }}
            </div>

            <form @submit.prevent="handleSubmit" class="mt-4 space-y-4">
              <div>
                <BaseSelect
                  label="Entity Type"
                  id="entityType"
                  v-model="formData.entity_type"
                  :options="[
                    { value: 'person', label: 'Person' },
                    { value: 'company', label: 'Company' },
                    { value: 'domain', label: 'Domain' },
                    { value: 'ip_address', label: 'IP Address' }
                  ]"
                />
              </div>

              <div v-if="formData.entity_type === 'person'" class="space-y-4">
                <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <BaseInput label="First Name" id="firstName" v-model="formData.data.first_name" />
                  <BaseInput label="Last Name" id="lastName" v-model="formData.data.last_name" />
                </div>
              </div>

              <div v-if="formData.entity_type === 'company'" class="space-y-4">
                <BaseInput label="Company Name" id="companyName" v-model="formData.data.name" required />
              </div>

              <div v-if="formData.entity_type === 'domain'" class="space-y-4">
                <BaseInput
                  label="Domain Name"
                  id="domain"
                  v-model="formData.data.domain"
                  placeholder="example.com"
                  required
                />
                <BaseInput
                  label="Description"
                  id="domain_description"
                  v-model="formData.data.description"
                  type="textarea"
                  placeholder="Add any notes or context about this domain"
                />
              </div>

              <div v-if="formData.entity_type === 'ip_address'" class="space-y-4">
                <BaseInput
                  label="IP Address"
                  id="ip_address"
                  v-model="formData.data.ip_address"
                  placeholder="192.168.1.1"
                  required
                />
                <BaseInput
                  label="Description"
                  id="ip_description"
                  v-model="formData.data.description"
                  type="textarea"
                  placeholder="Add any notes or context about this IP address"
                />
              </div>

              <div class="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                <button
                  type="submit"
                  :disabled="creating"
                  class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-cyan-600 text-base font-medium text-white hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  {{ creating ? 'Adding...' : 'Add Entity' }}
                </button>
                <button
                  type="button"
                  @click="$emit('close')"
                  class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:mt-0 sm:w-auto sm:text-sm dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
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
import { watch } from 'vue';
import { entityService } from '../services/entity';
import { useForm } from '../composables/useForm';
import { cleanFormData } from '../utils/cleanFormData';
import BaseInput from './BaseInput.vue';
import BaseSelect from './BaseSelect.vue';

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  caseId: { type: String, required: true },
});

const emit = defineEmits(['close', 'created']);

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