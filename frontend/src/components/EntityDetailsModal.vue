<template>
  <v-dialog v-model="dialogVisible" max-width="900px" persistent scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start :icon="getEntityIcon" color="primary" />
        <span class="text-h5">{{ getEntityTitle }}</span>
        <v-spacer />
        <v-chip 
          :color="isEditing ? 'warning' : 'primary'" 
          variant="tonal" 
          size="small"
        >
          {{ isEditing ? 'Editing' : 'View Mode' }}
        </v-chip>
      </v-card-title>
      
      <v-divider />
      
      <v-card-text class="pa-0">
        <!-- Error Alert -->
        <v-alert v-if="error" type="error" variant="tonal" class="ma-4">
          {{ error }}
        </v-alert>

        <!-- Tabs -->
        <v-tabs 
          v-model="activeTab" 
          color="primary" 
          align-tabs="start"
          class="border-b"
        >
          <v-tab
            v-for="(section, key) in entitySchema"
            :key="key"
            :value="key"
            :prepend-icon="getSectionIcon(key)"
          >
            {{ section.title }}
          </v-tab>
        </v-tabs>

        <!-- Tab Contents -->
        <v-tabs-window v-model="activeTab" class="pa-4">
              <v-tabs-window-item
                v-for="(section, key) in entitySchema"
                :key="key"
                :value="key"
              >
                <!-- Edit Mode Form -->
                <v-form v-if="isEditing" @submit.prevent="handleSubmit" ref="formRef">
                  <v-container fluid class="pa-0">
                    <v-row>
                      <template v-for="field in section.fields" :key="field.id">
                        <v-col :cols="field.gridCols === 2 ? 12 : 6">
                          <v-textarea
                            v-if="field.type === 'textarea'"
                            v-model="formData.data[section.parentField ? `${section.parentField}.${field.id}` : field.id]"
                            :label="field.label"
                            variant="outlined"
                            density="comfortable"
                            rows="3"
                            auto-grow
                            clearable
                          />
                          <v-text-field
                            v-else
                            v-model="formData.data[section.parentField ? `${section.parentField}.${field.id}` : field.id]"
                            :label="field.label"
                            :type="field.type"
                            variant="outlined"
                            density="comfortable"
                            clearable
                            :prepend-inner-icon="getFieldIcon(field.type)"
                          />
                        </v-col>
                      </template>
                    </v-row>
                  </v-container>
                </v-form>

                <!-- View Mode -->
                <v-container v-else fluid class="pa-0">
                  <v-row>
                    <template v-for="field in section.fields" :key="field.id">
                      <v-col :cols="field.gridCols === 2 ? 12 : 6">
                        <v-card variant="outlined" class="pa-3">
                          <v-card-subtitle class="pa-0 pb-2">
                            <v-icon 
                              :icon="getFieldIcon(field.type)" 
                              size="small" 
                              class="me-2"
                            />
                            {{ field.label }}
                          </v-card-subtitle>
                          
                          <!-- Associates Section -->
                          <div v-if="section.parentField === 'associates'">
                            <div v-if="getAssociateEntities(field.id).length > 0" class="mb-2">
                              <EntityTag
                                v-for="associate in getAssociateEntities(field.id)"
                                :key="associate.id"
                                @click="$emit('viewEntity', associate)"
                                class="ma-1"
                              >
                                {{ getEntityDisplayName(associate) }}
                              </EntityTag>
                            </div>
                            <v-chip v-else variant="text" color="grey" size="small">
                              {{ getFieldValue(entity.data, section.parentField, field.id) || 'Not specified' }}
                            </v-chip>
                          </div>
                          
                          <!-- URL Fields -->
                          <div v-else-if="field.type === 'url'">
                            <v-btn
                              v-if="getFieldValue(entity.data, section.parentField, field.id)"
                              :href="getFieldValue(entity.data, section.parentField, field.id)"
                              target="_blank"
                              variant="outlined"
                              color="primary"
                              size="small"
                              prepend-icon="mdi-open-in-new"
                              class="ma-0"
                            >
                              {{ getFieldValue(entity.data, section.parentField, field.id) }}
                            </v-btn>
                            <v-chip v-else variant="text" color="grey" size="small">
                              Not provided
                            </v-chip>
                          </div>
                          
                          <!-- Regular Fields -->
                          <div v-else class="text-body-1">
                            <span v-if="getFieldValue(entity.data, section.parentField, field.id)">
                              {{ getFieldValue(entity.data, section.parentField, field.id) }}
                            </span>
                            <v-chip v-else variant="text" color="grey" size="small">
                              Not provided
                            </v-chip>
                          </div>
                        </v-card>
                      </v-col>
                    </template>
                  </v-row>
                </v-container>
              </v-tabs-window-item>
            </v-tabs-window>

      </v-card-text>
      
      <v-divider />
      
      <v-card-actions class="pa-4">
        <v-spacer />
        
        <!-- Edit Mode Actions -->
        <template v-if="isEditing">
          <v-btn
            variant="text"
            prepend-icon="mdi-close"
            @click="cancelEdit"
            :disabled="updating"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-content-save"
            @click="handleSubmit"
            :disabled="updating"
            :loading="updating"
          >
            {{ updating ? 'Saving...' : 'Save Changes' }}
          </v-btn>
        </template>
        
        <!-- View Mode Actions -->
        <template v-else>
          <v-btn
            variant="text"
            prepend-icon="mdi-close"
            @click="$emit('close')"
          >
            Close
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-pencil"
            @click="startEditing"
          >
            Edit Entity
          </v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { entityService } from '../services/entity';
import { entitySchemas } from '../composables/entitySchemas';
import { cleanFormData } from '../utils/cleanFormData';
import EntityTag from './EntityTag.vue';
// Vuetify components are auto-imported

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  entity: { type: Object, required: true },
  caseId: { type: Number, required: true },
  existingEntities: { type: Array, required: true },
});

const emit = defineEmits(['close', 'edit', 'viewEntity']);

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
});
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
  
  Object.entries(schema).forEach(([, section]) => {
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
      
      Object.entries(schema).forEach(([, section]) => {
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

const getEntityIcon = computed(() => {
  const iconMap = {
    person: 'mdi-account',
    company: 'mdi-domain',
    domain: 'mdi-web',
    ip_address: 'mdi-ip',
    network: 'mdi-server-network'
  };
  return iconMap[props.entity.entity_type] || 'mdi-help-circle';
});

const getSectionIcon = (sectionKey) => {
  const iconMap = {
    basicInfo: 'mdi-information',
    address: 'mdi-map-marker',
    social_media: 'mdi-share-variant',
    associates: 'mdi-account-group',
    executives: 'mdi-account-tie',
    affiliates: 'mdi-handshake',
    contact: 'mdi-phone',
    technical: 'mdi-server',
    notes: 'mdi-note-text'
  };
  return iconMap[sectionKey] || 'mdi-folder';
};

const getFieldIcon = (fieldType) => {
  const iconMap = {
    email: 'mdi-email',
    tel: 'mdi-phone',
    url: 'mdi-link',
    textarea: 'mdi-text',
    text: 'mdi-form-textbox',
    number: 'mdi-numeric',
    date: 'mdi-calendar'
  };
  return iconMap[fieldType] || 'mdi-form-textbox';
};

const getFieldValue = (data, parentField, fieldId) => {
  if (parentField) {
    return data[parentField]?.[fieldId];
  }
  return data[fieldId];
};

</script>