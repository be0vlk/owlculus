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
import { ref, computed, toRef } from 'vue'
import EntityTag from './EntityTag.vue'
import { useEntityDetails } from '../composables/useEntityDetails'
import { useEntityAssociates } from '../composables/useEntityAssociates'
import { useEntityIcons } from '../composables/useEntityIcons'
import { useEntityDisplay } from '../composables/useEntityDisplay'

const props = defineProps({
  show: { type: Boolean, required: true, default: false },
  entity: { type: Object, required: true },
  caseId: { type: Number, required: true },
  existingEntities: { type: Array, required: true },
})

const emit = defineEmits(['close', 'edit', 'viewEntity'])

const dialogVisible = computed({
  get: () => props.show,
  set: (value) => {
    if (!value) {
      emit('close')
    }
  }
})

const entity = toRef(props, 'entity')
const caseId = toRef(props, 'caseId')
const existingEntities = toRef(props, 'existingEntities')

const {
  error,
  isEditing,
  updating,
  activeTab,
  formData,
  entitySchema,
  startEditing,
  cancelEdit,
  updateEntity
} = useEntityDetails(entity, caseId)

const {
  getAssociateEntities,
  processAssociates
} = useEntityAssociates(entity, existingEntities, caseId)

const {
  getEntityIcon,
  getSectionIcon,
  getFieldIcon
} = useEntityIcons(entity)

const {
  getEntityDisplayName,
  getEntityTitle,
  getFieldValue
} = useEntityDisplay(entity)

async function handleSubmit() {
  try {
    const { updatedEntity, createdAssociates } = await updateEntity(processAssociates)
    
    if (createdAssociates.length > 0) {
      emit('edit', updatedEntity, createdAssociates)
    } else {
      emit('edit', updatedEntity)
    }
  } catch (err) {
    // Error handled in composable
  }
}

</script>