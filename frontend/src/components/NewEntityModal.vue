<template>
  <v-dialog v-model="dialogVisible" max-width="700px" persistent>
    <v-card prepend-icon="mdi-account-plus" title="Add New Entity">
      <v-card-text>
        <!-- Error Alert -->
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
          {{ error }}
        </v-alert>

        <v-form ref="formRef" @submit.prevent="handleSubmit">
          <!-- Entity Type Selector -->
          <v-card variant="outlined" class="mb-6">
            <v-card-title class="text-subtitle-1 pb-2">
              <v-icon start>mdi-shape</v-icon>
              Entity Type
            </v-card-title>
            
            <v-card-text class="pt-0">
              <v-tabs 
                v-model="selectedTab" 
                color="primary" 
                align-tabs="start"
                @update:model-value="handleTabChange"
              >
                <v-tab 
                  v-for="entityType in entityTypes" 
                  :key="entityType.value"
                  :value="entityType.value"
                  :prepend-icon="entityType.icon"
                >
                  {{ entityType.title }}
                </v-tab>
              </v-tabs>
            </v-card-text>
          </v-card>

          <!-- Entity Form Content -->
          <v-tabs-window v-model="selectedTab">
            <!-- Person Form -->
            <v-tabs-window-item value="person">
              <v-card variant="outlined">
                <v-card-title class="text-subtitle-1">
                  <v-icon start>mdi-account</v-icon>
                  Person Details
                </v-card-title>
                
                <v-card-text>
                  <v-row>
                    <v-col cols="12" md="6">
                      <v-text-field
                        v-model="formData.data.first_name"
                        label="First Name"
                        variant="outlined"
                        density="comfortable"
                        prepend-inner-icon="mdi-account-outline"
                      />
                    </v-col>
                    
                    <v-col cols="12" md="6">
                      <v-text-field
                        v-model="formData.data.last_name"
                        label="Last Name"
                        variant="outlined"
                        density="comfortable"
                        prepend-inner-icon="mdi-account-outline"
                      />
                    </v-col>
                  </v-row>
                </v-card-text>
              </v-card>
            </v-tabs-window-item>

            <!-- Company Form -->
            <v-tabs-window-item value="company">
              <v-card variant="outlined">
                <v-card-title class="text-subtitle-1">
                  <v-icon start>mdi-domain</v-icon>
                  Company Details
                </v-card-title>
                
                <v-card-text>
                  <v-text-field
                    v-model="formData.data.name"
                    label="Company Name"
                    variant="outlined"
                    density="comfortable"
                    prepend-inner-icon="mdi-domain"
                    required
                    placeholder="Enter company name"
                  />
                </v-card-text>
              </v-card>
            </v-tabs-window-item>

            <!-- Domain Form -->
            <v-tabs-window-item value="domain">
              <v-card variant="outlined">
                <v-card-title class="text-subtitle-1">
                  <v-icon start>mdi-web</v-icon>
                  Domain Details
                </v-card-title>
                
                <v-card-text>
                  <v-text-field
                    v-model="formData.data.domain"
                    label="Domain Name"
                    variant="outlined"
                    density="comfortable"
                    prepend-inner-icon="mdi-web"
                    placeholder="example.com"
                    required
                    class="mb-4"
                    :rules="[rules.domain]"
                  />
                  
                  <v-textarea
                    v-model="formData.data.description"
                    label="Description (Optional)"
                    variant="outlined"
                    density="comfortable"
                    rows="3"
                    placeholder="Add any notes or context about this domain"
                  />
                </v-card-text>
              </v-card>
            </v-tabs-window-item>

            <!-- IP Address Form -->
            <v-tabs-window-item value="ip_address">
              <v-card variant="outlined">
                <v-card-title class="text-subtitle-1">
                  <v-icon start>mdi-ip</v-icon>
                  IP Address Details
                </v-card-title>
                
                <v-card-text>
                  <v-text-field
                    v-model="formData.data.ip_address"
                    label="IP Address"
                    variant="outlined"
                    density="comfortable"
                    prepend-inner-icon="mdi-ip"
                    placeholder="192.168.1.1"
                    required
                    class="mb-4"
                    :rules="[rules.ip]"
                  />
                  
                  <v-textarea
                    v-model="formData.data.description"
                    label="Description (Optional)"
                    variant="outlined"
                    density="comfortable"
                    rows="3"
                    placeholder="Add any notes or context about this IP address"
                  />
                </v-card-text>
              </v-card>
            </v-tabs-window-item>
          </v-tabs-window>
        </v-form>
      </v-card-text>

      <v-divider />

      <v-card-actions>
        <v-spacer />
        <v-btn
          variant="text"
          @click="$emit('close')"
          :disabled="creating"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="flat"
          @click="handleSubmit"
          :disabled="creating || !isFormValid"
          :loading="creating"
        >
          Add Entity
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { watch, computed, ref } from 'vue';
import { entityService } from '../services/entity';
import { useForm } from '../composables/useForm';
import { cleanFormData } from '../utils/cleanFormData';

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  caseId: { type: String, required: true },
});

const emit = defineEmits(['close', 'created']);

// Reactive variables
const selectedTab = ref('person');
const formRef = ref(null);

// Entity types configuration
const entityTypes = [
  { value: 'person', title: 'Person', icon: 'mdi-account' },
  { value: 'company', title: 'Company', icon: 'mdi-domain' },
  { value: 'domain', title: 'Domain', icon: 'mdi-web' },
  { value: 'ip_address', title: 'IP Address', icon: 'mdi-ip' }
];

// Validation rules
const rules = {
  domain: (value) => {
    if (!value) return 'Domain is required';
    const domainPattern = /^[a-zA-Z0-9][a-zA-Z0-9-_]*\.{1}[a-zA-Z]{2,}$/;
    return domainPattern.test(value) || 'Please enter a valid domain name';
  },
  ip: (value) => {
    if (!value) return 'IP address is required';
    const ipPattern = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return ipPattern.test(value) || 'Please enter a valid IP address';
  }
};

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
});

const initialFormData = {
  entity_type: 'person',
  data: {
    social_media: { x: '', linkedin: '', facebook: '', instagram: '', tiktok: '', reddit: '', other: '' },
    domains: [],
    ip_addresses: [],
    subdomains: [],
  },
};

// Form validation
const isFormValid = computed(() => {
  if (!formData.entity_type) return false;
  
  switch (formData.entity_type) {
    case 'person':
      return formData.data.first_name || formData.data.last_name;
    case 'company':
      return formData.data.name;
    case 'domain':
      return formData.data.domain && rules.domain(formData.data.domain) === true;
    case 'ip_address':
      return formData.data.ip_address && rules.ip(formData.data.ip_address) === true;
    default:
      return false;
  }
});

const { formData, error, creating, handleSubmit } = useForm(initialFormData, async (formData) => {
  const submitData = {
    entity_type: formData.entity_type,
    data: cleanFormData({ ...formData.data }),
  };

  const response = await entityService.createEntity(props.caseId, submitData);
  emit('created', response);
  emit('close');
});

// Handle tab change
function handleTabChange(newTab) {
  formData.entity_type = newTab;
}

// Watch for entity type changes
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
  } else if (newType === 'domain') {
    Object.assign(formData.data, {
      domain: '',
      description: ''
    });
  } else if (newType === 'ip_address') {
    Object.assign(formData.data, {
      ip_address: '',
      description: ''
    });
  }
});

// Watch for tab changes to sync with form data
watch(selectedTab, (newTab) => {
  if (newTab !== formData.entity_type) {
    formData.entity_type = newTab;
  }
});

// Initialize form when dialog opens
watch(() => props.show, (show) => {
  if (show) {
    selectedTab.value = 'person';
    formData.entity_type = 'person';
  }
});
</script>