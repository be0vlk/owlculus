<template>
  <v-col :cols="field.gridCols === 2 || (field.type === 'array' && field.isArray) ? 12 : 6">
    <v-card variant="outlined" class="pa-3">
      <v-card-subtitle class="pa-0 pb-2">
        <v-icon
          :icon="
            section.parentField === 'social_media'
              ? getSocialMediaIcon(field.id)
              : getFieldIcon(field.type)
          "
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
          :prepend-icon="
            section.parentField === 'social_media'
              ? getSocialMediaIcon(field.id)
              : 'mdi-open-in-new'
          "
          class="ma-0"
        >
          {{ getFieldValue(entity.data, section.parentField, field.id) }}
        </v-btn>
        <v-chip v-else color="grey" size="small" variant="text"> Not provided </v-chip>

        <!-- Source for URL fields -->
        <div v-if="field.hasSource && sourceValue" class="mt-2">
          <v-chip color="blue-grey" prepend-icon="mdi-source-branch" size="small" variant="tonal">
            Source: {{ sourceValue }}
          </v-chip>
        </div>
      </div>

      <!-- Array Fields -->
      <div v-else-if="field.type === 'array' && field.isArray">
        <div v-if="arrayValue && arrayValue.length > 0">
          <v-data-table
            v-model:page="currentPage"
            v-model:items-per-page="itemsPerPage"
            :headers="subdomainHeaders"
            :items="arrayValue"
            :items-length="arrayValue.length"
            :items-per-page-options="[10, 25, 50, 100]"
            density="compact"
            class="elevation-0 subdomain-table"
            :loading="loading"
            item-key="subdomain"
            hover
            items-per-page-text="Subdomains per page:"
          >
            <template v-slot:top>
              <v-toolbar flat class="px-4">
                <v-spacer />
                <v-btn
                  variant="outlined"
                  size="small"
                  prepend-icon="mdi-download"
                  @click="exportSubdomains"
                >
                  Export
                </v-btn>
              </v-toolbar>
            </template>
            <template #[`item.subdomain`]="{ item }">
              <div class="d-flex align-center">
                <v-icon size="small" class="me-2">mdi-subdirectory-arrow-right</v-icon>
                <span class="text-body-2 font-weight-medium">{{ item.subdomain }}</span>
              </div>
            </template>
            <template #[`item.ip`]="{ item }">
              <div v-if="item.ip" class="d-flex align-center">
                <v-icon size="x-small" class="me-1">mdi-ip-network</v-icon>
                <span class="text-body-2">{{ item.ip }}</span>
              </div>
              <span v-else class="text-body-2 text-medium-emphasis">-</span>
            </template>
            <template #[`item.resolved`]="{ item }">
              <v-chip
                :color="item.resolved ? 'success' : 'error'"
                :prepend-icon="item.resolved ? 'mdi-check-circle' : 'mdi-close-circle'"
                size="small"
                variant="tonal"
              >
                {{ item.resolved ? 'Yes' : 'No' }}
              </v-chip>
            </template>
            <template #[`item.source`]="{ item }">
              <div v-if="item.source" class="d-flex align-center">
                <v-icon size="x-small" class="me-1">mdi-source-branch</v-icon>
                <span class="text-body-2">{{ item.source }}</span>
              </div>
              <span v-else class="text-body-2 text-medium-emphasis">-</span>
            </template>
          </v-data-table>
        </div>
        <v-chip v-else color="grey" size="small" variant="text"> No subdomains discovered </v-chip>
      </div>

      <!-- Regular Fields -->
      <div v-else class="text-body-1">
        <span v-if="regularValue">
          {{ regularValue }}
        </span>
        <v-chip v-else color="grey" size="small" variant="text"> Not provided </v-chip>

        <!-- Source for regular fields -->
        <div v-if="field.hasSource && sourceValue" class="mt-2">
          <v-chip color="blue-grey" prepend-icon="mdi-source-branch" size="small" variant="tonal">
            Source: {{ sourceValue }}
          </v-chip>
        </div>
      </div>
    </v-card>
  </v-col>
</template>

<script setup>
import { computed, ref } from 'vue'
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
  existingEntities: { type: Array, required: true },
})

defineEmits(['viewEntity'])

const { getFieldIcon, getSocialMediaIcon } = useEntityIcons(props.entity)
const { getEntityDisplayName, getFieldValue } = useEntityDisplay(props.entity)

const regularValue = computed(() =>
  getFieldValue(props.entity.data, props.section.parentField, props.field.id),
)

const currentPage = ref(1)
const itemsPerPage = ref(10)
const loading = ref(false)

const arrayValue = computed(() =>
  getFieldValue(props.entity.data, props.section.parentField, props.field.id),
)

const subdomainHeaders = computed(() => [
  { title: 'Subdomain', value: 'subdomain', sortable: true },
  { title: 'IP Address', value: 'ip', sortable: true },
  { title: 'Resolved', value: 'resolved', sortable: true },
  { title: 'Source', value: 'source', sortable: true },
])

const exportSubdomains = () => {
  try {
    const subdomains = arrayValue.value || []

    if (subdomains.length === 0) {
      return
    }

    const headers = ['Subdomain', 'IP Address', 'Resolved', 'Source']
    const csvData = [
      headers.join(','),
      ...subdomains.map((item) =>
        [
          `"${(item.subdomain || '').replace(/"/g, '""')}"`,
          `"${(item.ip || '').replace(/"/g, '""')}"`,
          item.resolved ? 'Yes' : 'No',
          `"${(item.source || '').replace(/"/g, '""')}"`,
        ].join(','),
      ),
    ].join('\n')

    const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute(
      'download',
      `subdomains-${props.field.label.toLowerCase().replace(/\s+/g, '-')}-${new Date().toISOString().split('T')[0]}.csv`,
    )
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Error exporting subdomains:', error)
  }
}
</script>

<style scoped>
.subdomain-table :deep(.v-data-table__td) {
  padding: 8px 16px;
}

.subdomain-table :deep(.v-data-table__th) {
  padding: 8px 16px;
  font-weight: 600;
}
</style>
