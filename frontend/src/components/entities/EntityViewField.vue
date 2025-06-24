<template>
  <v-col :cols="field.gridCols === 2 || (field.type === 'array' && field.isArray) ? 12 : 6">
    <v-card variant="outlined" class="pa-3">
      <v-card-subtitle class="pa-0 pb-2">
        <v-icon
          :icon="section.parentField === 'social_media' ? getSocialMediaIcon(field.id) : getFieldIcon(field.type)"
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
          :href="ensureProtocol(getFieldValue(entity.data, section.parentField, field.id))"
          target="_blank"
          variant="outlined"
          color="primary"
          size="small"
          :prepend-icon="section.parentField === 'social_media' ? getSocialMediaIcon(field.id) : 'mdi-open-in-new'"
          class="ma-0"
        >
          {{ getFieldValue(entity.data, section.parentField, field.id) }}
        </v-btn>
        <v-chip v-else variant="text" color="grey" size="small">
          Not provided
        </v-chip>

        <!-- Source for URL fields -->
        <div v-if="field.hasSource && sourceValue" class="mt-2">
          <v-chip
            color="blue-grey"
            variant="tonal"
            size="small"
            prepend-icon="mdi-source-branch"
          >
            Source: {{ sourceValue }}
          </v-chip>
        </div>
      </div>

      <!-- Array Fields -->
      <div v-else-if="field.type === 'array' && field.isArray">
        <div v-if="arrayValue && arrayValue.length > 0">
          <v-data-table
            :headers="subdomainHeaders"
            :items="arrayValue"
            density="compact"
            hide-default-footer
            :items-per-page="-1"
            class="elevation-0"
          >
            <template #[`item.subdomain`]="{ item }">
              <div class="d-flex align-center">
                <v-icon size="small" class="mr-2">mdi-subdirectory-arrow-right</v-icon>
                <span class="font-weight-medium">{{ item.subdomain }}</span>
              </div>
            </template>
            <template #[`item.ip`]="{ item }">
              <div v-if="item.ip" class="d-flex align-center">
                <v-icon size="x-small" class="mr-1">mdi-ip-network</v-icon>
                {{ item.ip }}
              </div>
              <span v-else class="text-grey">-</span>
            </template>
            <template #[`item.resolved`]="{ item }">
              <div class="d-flex align-center">
                <v-icon 
                  size="x-small" 
                  class="mr-1"
                  :color="item.resolved ? 'success' : 'error'"
                >
                  {{ item.resolved ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                {{ item.resolved ? 'Yes' : 'No' }}
              </div>
            </template>
            <template #[`item.source`]="{ item }">
              <div v-if="item.source" class="d-flex align-center">
                <v-icon size="x-small" class="mr-1">mdi-source-branch</v-icon>
                {{ item.source }}
              </div>
              <span v-else class="text-grey">-</span>
            </template>
          </v-data-table>
        </div>
        <v-chip v-else variant="text" color="grey" size="small">
          No subdomains discovered
        </v-chip>
      </div>

      <!-- Regular Fields -->
      <div v-else class="text-body-1">
        <span v-if="regularValue">
          {{ regularValue }}
        </span>
        <v-chip v-else variant="text" color="grey" size="small">
          Not provided
        </v-chip>

        <!-- Source for regular fields -->
        <div v-if="field.hasSource && sourceValue" class="mt-2">
          <v-chip
            color="blue-grey"
            variant="tonal"
            size="small"
            prepend-icon="mdi-source-branch"
          >
            Source: {{ sourceValue }}
          </v-chip>
        </div>
      </div>
    </v-card>
  </v-col>
</template>

<script setup>
import { computed } from 'vue'
import EntityTag from './EntityTag.vue'
import { useEntityIcons } from '../../composables/useEntityIcons.js'
import { useEntityDisplay } from '../../composables/useEntityDisplay.js'
import { ensureProtocol } from '../../utils/urlHelpers.js'

const props = defineProps({
  field: { type: Object, required: true },
  section: { type: Object, required: true },
  entity: { type: Object, required: true },
  sourceValue: { type: String, default: '' },
  getAssociateEntities: { type: Function, required: true },
  existingEntities: { type: Array, required: true }
})

defineEmits(['viewEntity'])

const { getFieldIcon, getSocialMediaIcon } = useEntityIcons(props.entity)
const { getEntityDisplayName, getFieldValue } = useEntityDisplay(props.entity)

const regularValue = computed(() => 
  getFieldValue(props.entity.data, props.section.parentField, props.field.id)
)

const arrayValue = computed(() => 
  getFieldValue(props.entity.data, props.section.parentField, props.field.id)
)

const subdomainHeaders = computed(() => [
  { title: 'Subdomain', value: 'subdomain', sortable: true },
  { title: 'IP Address', value: 'ip', sortable: true },
  { title: 'Resolved', value: 'resolved', sortable: true },
  { title: 'Source', value: 'source', sortable: true }
])
</script>