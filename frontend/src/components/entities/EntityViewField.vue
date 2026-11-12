<template>
  <v-col cols="12" :md="field.gridCols === 2 || (field.type === 'array' && field.isArray) ? 12 : 6">
    <v-card variant="outlined" class="pa-3">
      <v-card-subtitle class="pa-0 pb-2">
        <v-icon
          :icon="
            section.parentField === 'social_media'
              ? socialMediaIcon(field.id)
              : fieldIcon(field.type)
          "
          size="small"
          class="me-2"
        />
        {{ field.label }}
      </v-card-subtitle>

      <div v-if="section.parentField === 'associates'">
        <v-chip variant="text" color="grey" size="small">
          {{ value || 'Not specified' }}
        </v-chip>
      </div>

      <div v-else-if="field.type === 'url'">
        <v-btn
          v-if="value"
          :href="ensureProtocol(value)"
          target="_blank"
          variant="outlined"
          color="primary"
          size="small"
          :prepend-icon="
            section.parentField === 'social_media' ? socialMediaIcon(field.id) : 'mdi-open-in-new'
          "
          class="ma-0"
        >
          {{ value }}
        </v-btn>
        <v-chip v-else color="grey" size="small" variant="text"> Not provided </v-chip>

        <div v-if="field.hasSource && sourceValue" class="mt-2">
          <v-chip color="blue-grey" prepend-icon="mdi-source-branch" size="small" variant="tonal">
            Source: {{ sourceValue }}
          </v-chip>
        </div>
      </div>

      <div v-else-if="field.type === 'array' && field.isArray">
        <div v-if="value?.length">
          <v-data-table
            :headers="SUBDOMAIN_HEADERS"
            :items="value"
            :items-per-page="10"
            :items-per-page-options="[10, 25, 50, 100]"
            density="compact"
            class="elevation-0 subdomain-table"
            item-value="subdomain"
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
                <span class="text-body-medium font-weight-medium">{{ item.subdomain }}</span>
              </div>
            </template>
            <template #[`item.ip`]="{ item }">
              <div v-if="item.ip" class="d-flex align-center">
                <v-icon size="x-small" class="me-1">mdi-ip-network</v-icon>
                <span class="text-body-medium">{{ item.ip }}</span>
              </div>
              <span v-else class="text-body-medium text-medium-emphasis">-</span>
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
                <span class="text-body-medium">{{ item.source }}</span>
              </div>
              <span v-else class="text-body-medium text-medium-emphasis">-</span>
            </template>
          </v-data-table>
        </div>
        <v-chip v-else color="grey" size="small" variant="text"> No subdomains discovered </v-chip>
      </div>

      <div v-else class="text-body-large">
        <span v-if="value">
          {{ value }}
        </span>
        <v-chip v-else color="grey" size="small" variant="text"> Not provided </v-chip>

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
import { computed } from 'vue'
import { fieldIcon, socialMediaIcon } from '../../composables/entityTypes.js'
import { ensureProtocol } from '../../utils/urlHelpers.js'
import { downloadBlob } from '../../utils/download.js'

const props = defineProps({
  field: { type: Object, required: true },
  section: { type: Object, required: true },
  entity: { type: Object, required: true },
  sourceValue: { type: String, default: '' },
})

const value = computed(() => {
  const { data } = props.entity
  const parent = props.section.parentField
  return parent ? data[parent]?.[props.field.id] : data[props.field.id]
})

const SUBDOMAIN_HEADERS = [
  { title: 'Subdomain', value: 'subdomain', sortable: true },
  { title: 'IP Address', value: 'ip', sortable: true },
  { title: 'Resolved', value: 'resolved', sortable: true },
  { title: 'Source', value: 'source', sortable: true },
]

const csvCell = (text) => `"${(text || '').replace(/"/g, '""')}"`

const exportSubdomains = () => {
  const csv = [
    'Subdomain,IP Address,Resolved,Source',
    ...value.value.map((item) =>
      [
        csvCell(item.subdomain),
        csvCell(item.ip),
        item.resolved ? 'Yes' : 'No',
        csvCell(item.source),
      ].join(','),
    ),
  ].join('\n')
  const label = props.field.label.toLowerCase().replace(/\s+/g, '-')
  downloadBlob(
    { blob: new Blob([csv], { type: 'text/csv;charset=utf-8;' }) },
    `subdomains-${label}-${new Date().toISOString().split('T')[0]}.csv`,
  )
}
</script>
