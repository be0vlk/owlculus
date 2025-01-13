<template>
  <div v-if="show" class="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
    <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
      <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" @click="$emit('close')"></div>

      <div class="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full sm:p-6">
        <div class="sm:flex sm:items-start">
          <div class="mt-3 text-center sm:mt-0 sm:text-left w-full">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg leading-6 font-medium text-gray-900 dark:text-white" id="modal-title">
                {{ getEntityTitle }}
              </h3>
              <button
                @click="$emit('close')"
                class="rounded-md text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              >
                <span class="sr-only">Close</span>
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div v-if="error" class="mt-2 p-2 bg-red-100 text-red-700 rounded-md text-sm">
              {{ error }}
            </div>

            <!-- Tabs -->
            <div class="mt-4">
              <ul class="flex flex-wrap -mb-px text-sm font-medium text-center" role="tablist">
                <li v-for="(section, key) in entitySchema" :key="key" class="mr-2">
                  <a
                    href="#"
                    @click.prevent="activeTab = key"
                    :class="[
                      'inline-block p-4 rounded-t-lg border-b-2',
                      activeTab === key 
                        ? 'text-cyan-600 border-cyan-600 dark:text-cyan-500 dark:border-cyan-500' 
                        : 'text-gray-500 border-transparent hover:text-gray-600 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                    ]"
                    role="tab"
                    :aria-selected="activeTab === key"
                  >
                    {{ section.title }}
                  </a>
                </li>
              </ul>
            </div>

            <!-- Tab Contents -->
            <div class="mt-4">
              <form v-if="isEditing" @submit.prevent="handleSubmit" class="space-y-4">
                <div v-for="(section, key) in entitySchema" :key="key" v-show="activeTab === key" class="space-y-4">
                  <div class="grid grid-cols-1 gap-4" :class="{ 'sm:grid-cols-2': section.fields.some(f => f.gridCols === 2) }">
                    <template v-for="field in section.fields" :key="field.id">
                      <BaseInput
                        :label="field.label"
                        :id="field.id"
                        :type="field.type"
                        v-model="formData.data[section.parentField ? `${section.parentField}.${field.id}` : field.id]"
                        :class="{ 'col-span-2': field.gridCols === 2 }"
                      />
                    </template>
                  </div>
                </div>

                <div class="mt-6 sm:flex sm:flex-row-reverse">
                  <button
                    type="submit"
                    :disabled="updating"
                    class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-cyan-600 text-base font-medium text-white hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    {{ updating ? 'Saving...' : 'Save Changes' }}
                  </button>
                  <button
                    type="button"
                    @click="cancelEdit"
                    class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:mt-0 sm:w-auto sm:text-sm dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
                  >
                    Cancel
                  </button>
                </div>
              </form>

              <div v-else>
                <div v-for="(section, key) in entitySchema" :key="key" v-show="activeTab === key" class="space-y-4">
                  <div class="grid grid-cols-1 gap-4" :class="{ 'sm:grid-cols-2': section.fields.some(f => f.gridCols === 2) }">
                    <template v-for="field in section.fields" :key="field.id">
                      <div :class="{ 'col-span-2': field.gridCols === 2 }">
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          {{ field.label }}
                        </label>
                        <div v-if="section.parentField === 'associates'" class="mt-1">
                          <div v-if="getAssociateEntities(field.id).length > 0" class="mb-2">
                            <EntityTag
                              v-for="associate in getAssociateEntities(field.id)"
                              :key="associate.id"
                              @click="$emit('viewEntity', associate)"
                            >
                              {{ getEntityDisplayName(associate) }}
                            </EntityTag>
                          </div>
                          <div v-else class="text-sm text-gray-500 dark:text-gray-400">
                            {{ getFieldValue(entity.data, section.parentField, field.id) || '' }}
                          </div>
                        </div>
                        <div v-else-if="field.type === 'url'" class="mt-1 text-sm">
                          <a 
                            v-if="getFieldValue(entity.data, section.parentField, field.id)"
                            :href="getFieldValue(entity.data, section.parentField, field.id)"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="text-cyan-600 hover:text-cyan-500 dark:text-cyan-400 dark:hover:text-cyan-300"
                          >
                            {{ getFieldValue(entity.data, section.parentField, field.id) }}
                          </a>
                          <span v-else class="text-gray-500 dark:text-gray-400">-</span>
                        </div>
                        <div v-else class="mt-1 text-sm text-gray-900 dark:text-gray-100">
                          {{ getFieldValue(entity.data, section.parentField, field.id) || '' }}
                        </div>
                      </div>
                    </template>
                  </div>
                </div>

                <div class="mt-6 sm:flex sm:flex-row-reverse">
                  <button
                    type="button"
                    @click="startEditing"
                    class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-cyan-600 text-base font-medium text-white hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    Edit Entity
                  </button>
                  <button
                    type="button"
                    @click="$emit('close')"
                    class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:mt-0 sm:w-auto sm:text-sm dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { entityService } from '../services/entity';
import { entitySchemas } from '../composables/entitySchemas';
import { cleanFormData } from '../utils/cleanFormData';
import EntityTag from './EntityTag.vue';
import BaseInput from './BaseInput.vue';

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  entity: { type: Object, required: true },
  caseId: { type: Number, required: true },
  existingEntities: { type: Array, required: true },
});

const emit = defineEmits(['close', 'edit', 'viewEntity']);
const error = ref('');
const isEditing = ref(false);
const updating = ref(false);
const activeTab = ref('basicInfo'); // Default active tab

const formData = ref({
  data: {
    address: {},
    social_media: {},
    aliases: []
  },
});

const associateEntityMap = ref(new Map());

const getEntityDisplayName = (entity) => {
  if (entity.entity_type === 'person') {
    return `${entity.data.first_name} ${entity.data.last_name}`.trim();
  }
  return entity.data.name || 'Unnamed Entity';
};

const getAssociateEntities = (fieldId) => {
  return associateEntityMap.value.get(fieldId) || [];
};

watch(() => props.entity, async (newEntity) => {
  if (newEntity) {
    formData.value.data.social_media = newEntity.data.social_media
    formData.value.data.aliases = newEntity.data.aliases
  }
})

const entitySchema = computed(() => {
  return entitySchemas[props.entity.entity_type];
});

// Set the active tab to the first one whenever the entity changes
watch(() => props.entity, () => {
  activeTab.value = Object.keys(entitySchema.value)[0];
});

// Helper function to flatten nested fields for form data
function flattenNestedFields(data, schema) {
  const result = { ...data };
  
  Object.entries(schema).forEach(([sectionKey, section]) => {
    if (section.parentField && data[section.parentField]) {
      // For each field in the section, create a dot notation entry
      section.fields.forEach(field => {
        const value = data[section.parentField][field.id];
        if (value !== undefined) {
          result[`${section.parentField}.${field.id}`] = value;
        }
      });
    }
  });
  
  return result;
}

function startEditing() {
  // Initialize form data with all possible fields
  const initialData = {
    ...props.entity.data,
    aliases: Array.isArray(props.entity.data.aliases) ? [...props.entity.data.aliases] : [],
    address: props.entity.data.address || {},
    social_media: props.entity.data.social_media || {},
    associates: props.entity.data.associates || {},
    executives: props.entity.data.executives || {},
    affiliates: props.entity.data.affiliates || {}
  };

  // Flatten nested fields for the form
  const flattenedData = flattenNestedFields(initialData, entitySchema.value);

  formData.value = {
    data: flattenedData
  };
  isEditing.value = true;
}

function cancelEdit() {
  isEditing.value = false;
  error.value = '';
}

async function handleSubmit() {
  try {
    updating.value = true;
    error.value = '';

    // Clean and prepare all nested data
    const cleanedData = cleanFormData({ ...formData.value.data });
    
    // Restructure nested fields
    const restructureNestedFields = (data, schema) => {
      const result = { ...data };
      
      Object.entries(schema).forEach(([sectionKey, section]) => {
        if (section.parentField) {
          // Initialize the parent field if it doesn't exist
          result[section.parentField] = result[section.parentField] || {};
          
          // Move any dot-notation fields to their proper nested structure
          section.fields.forEach(field => {
            const dotKey = `${section.parentField}.${field.id}`;
            if (dotKey in result) {
              result[section.parentField][field.id] = result[dotKey];
              delete result[dotKey];
            }
          });
        }
      });
      
      return result;
    };

    const restructuredData = restructureNestedFields(cleanedData, entitySchema.value);
    
    const submitData = {
      data: {
        ...restructuredData,
        aliases: Array.isArray(restructuredData.aliases) ? restructuredData.aliases : [],
        social_media: restructuredData.social_media || {},
        associates: restructuredData.associates || {},
        executives: restructuredData.executives || {},
        affiliates: restructuredData.affiliates || {},
        address: restructuredData.address || {}
      },
    };

    // First update the current entity
    const updatedEntity = await entityService.updateEntity(props.caseId, props.entity.id, {
      entity_type: props.entity.entity_type,
      data: submitData.data,
    });

    // If this is a person entity, handle associates
    if (props.entity.entity_type === 'person' && submitData.data.associates) {
      const associateFields = ['children', 'colleagues', 'father', 'friends', 'mother', 'partner/spouse', 'siblings', 'other'];
      const createdAssociates = [];
      associateEntityMap.value.clear();

      for (const field of associateFields) {
        const associateNames = submitData.data.associates[field];
        if (associateNames) {
          // Split by commas and handle multiple names
          const names = associateNames.split(',').map(name => name.trim()).filter(name => name);
          const fieldAssociates = [];
          
          for (const name of names) {
            try {
              // Parse the name
              const [firstName, ...lastNameParts] = name.split(' ');
              const lastName = lastNameParts.join(' ');
              
              // Check if this person already exists
              let associateEntity = findExistingEntity(firstName, lastName);
              
              // Get the current entity's name for the reciprocal relationship
              const currentEntityName = `${submitData.data.first_name} ${submitData.data.last_name}`.trim();
              
              if (!associateEntity) {
                // Create a new person entity if they don't exist
                associateEntity = await entityService.createEntity(props.caseId, {
                  entity_type: 'person',
                  data: {
                    first_name: firstName || name,
                    last_name: lastName || '',
                    associates: {
                      // Create a reciprocal association using the current entity's name
                      [field === 'partner/spouse' ? 'partner/spouse' :
                       field === 'father' ? 'children' :
                       field === 'mother' ? 'children' :
                       field === 'children' ? 'father' : // Note: This is an assumption, could be mother
                       field === 'siblings' ? 'siblings' :
                       field === 'colleagues' ? 'colleagues' :
                       field === 'friends' ? 'friends' : 'other']: currentEntityName
                    }
                  }
                });
                createdAssociates.push(associateEntity);
              } else {
                // Update the existing entity to add the reciprocal relationship
                const reciprocalField = field === 'partner/spouse' ? 'partner/spouse' :
                                      field === 'father' ? 'children' :
                                      field === 'mother' ? 'children' :
                                      field === 'children' ? 'father' :
                                      field === 'siblings' ? 'siblings' :
                                      field === 'colleagues' ? 'colleagues' :
                                      field === 'friends' ? 'friends' : 'other';
                
                const updatedAssociateData = {
                  ...associateEntity.data,
                  associates: {
                    ...associateEntity.data.associates,
                    [reciprocalField]: currentEntityName
                  }
                };
                
                associateEntity = await entityService.updateEntity(
                  props.caseId,
                  associateEntity.id,
                  {
                    entity_type: 'person',
                    data: updatedAssociateData
                  }
                );
              }
              
              fieldAssociates.push(associateEntity);
            } catch (err) {
              console.error(`Failed to handle associate entity for ${name}:`, err);
              // Continue with other associates even if one fails
            }
          }
          
          // Store the associates for this field
          if (fieldAssociates.length > 0) {
            associateEntityMap.value.set(field, fieldAssociates);
          }
        }
      }

      // Emit an event with both the updated entity and created associates
      emit('edit', updatedEntity, createdAssociates);
    } else {
      emit('edit', updatedEntity);
    }

    isEditing.value = false;
  } catch (err) {
    error.value = err.response?.data?.message || err.message || 'Failed to update entity';
  } finally {
    updating.value = false;
  }
}

// Helper function to find an existing entity by name
const findExistingEntity = (firstName, lastName) => {
  const fullName = `${firstName} ${lastName}`.trim().toLowerCase();
  return props.existingEntities.find(entity => 
    entity.entity_type === 'person' && 
    `${entity.data.first_name} ${entity.data.last_name}`.trim().toLowerCase() === fullName
  );
};

// When the entity prop changes, update the associate entity map
watch(() => props.entity, async (newEntity) => {
  if (newEntity?.entity_type === 'person' && newEntity.data.associates) {
    associateEntityMap.value.clear();
    const associateFields = ['children', 'colleagues', 'father', 'friends', 'mother', 'partner/spouse', 'siblings', 'other'];
    
    for (const field of associateFields) {
      const associateNames = newEntity.data.associates[field];
      if (associateNames) {
        try {
          // Split by commas and handle multiple names
          const names = associateNames.split(',').map(name => name.trim()).filter(name => name);
          const fieldAssociates = [];
          
          for (const name of names) {
            // Parse the name
            const [firstName, ...lastNameParts] = name.split(' ');
            const lastName = lastNameParts.join(' ');
            
            // Check if this person already exists
            let associateEntity = findExistingEntity(firstName, lastName);
            
            if (!associateEntity) {
              // This is a placeholder - you'll need to implement the actual entity lookup
              const existingEntity = {
                id: `temp_${field}_${name}`, // Temporary ID
                entity_type: 'person',
                data: {
                  first_name: firstName || name,
                  last_name: lastName || ''
                }
              };
              fieldAssociates.push(existingEntity);
            } else {
              fieldAssociates.push(associateEntity);
            }
          }
          
          // Store the associates for this field
          if (fieldAssociates.length > 0) {
            associateEntityMap.value.set(field, fieldAssociates);
          }
        } catch (err) {
          console.error(`Failed to load associate entities for ${field}:`, err);
        }
      }
    }
  }
}, { immediate: true });

const getEntityTitle = computed(() => {
  if (props.entity.entity_type === 'person') {
    return `${props.entity.data.first_name} ${props.entity.data.last_name}`;
  }
  return props.entity.data.name || 'Entity Details';
});

const getFieldValue = (data, parentField, fieldId) => {
  if (parentField) {
    return data[parentField]?.[fieldId];
  }
  return data[fieldId];
};
</script>