<template>
  <div class="d-flex flex-column ga-4">
    <p v-if="latestProgress" role="status" class="text-body-medium">
      {{ latestProgress.message }}: {{ latestProgress.count }} in this portion.
    </p>
    <p v-if="hasCorrelations" class="text-body-medium">
      {{ counts.entities }} source Entities · {{ counts.matches }} matches ·
      {{ counts.cases }} related Cases
    </p>
    <template v-for="resultItem in normalizedResult" :key="resultKey(resultItem)">
      <!-- Entity Match Card -->
      <v-card v-if="isGroup(resultItem)" elevation="1" rounded="lg">
        <!-- Entity Header -->
        <v-card-text class="border-b">
          <div class="d-flex align-center">
            <v-icon icon="mdi-link" class="mr-2" color="grey-darken-1" />
            <h3 class="text-title-large font-weight-medium">
              {{ entityLabel(resultItem.data) }}
            </h3>
            <v-chip class="ml-2" color="primary" size="small" variant="tonal">
              {{ resultItem.data.entity_type }}
            </v-chip>
            <v-chip
              class="ml-2"
              size="small"
              :color="getMatchTypeColor(resultItem.data.match_type)"
              variant="tonal"
            >
              {{ getMatchTypeLabel(resultItem.data.match_type) }}
            </v-chip>
          </div>

          <!-- Correlation Context -->
          <div class="mt-2 text-body-medium text-medium-emphasis">
            Shared {{ getMatchTypeLabel(resultItem.data.match_type).toLowerCase() }} value:
            <span class="font-weight-medium">{{
              resultItem.data.matched_value ||
              resultItem.data.domain ||
              resultItem.data.employer_name ||
              entityLabel(resultItem.data)
            }}</span
            >. This connection is an investigative lead; it does not establish identity.
            <p
              v-for="field in resultItem.data.source_fields || []"
              :key="field.field + field.value"
            >
              Source {{ field.field }}: {{ field.value }}
            </p>
          </div>
        </v-card-text>

        <!-- Matches List -->
        <v-card-text>
          <div class="d-flex flex-column ga-3">
            <v-card
              v-for="match in resultItem.data.matches"
              :key="`${match.case_id}:${match.entity_id}`"
              elevation="1"
              rounded="lg"
            >
              <v-card-text>
                <div class="d-flex justify-space-between align-start">
                  <div class="d-flex flex-column ga-1">
                    <h4 class="text-body-large font-weight-medium">
                      Case #{{ match.case_number }}
                    </h4>
                    <p class="text-body-medium text-medium-emphasis">
                      {{ match.case_title }}
                    </p>
                    <p class="text-body-medium text-secondary">
                      {{ entityLabel(match) }} ({{
                        match.entity_type || resultItem.data.entity_type
                      }})
                    </p>
                    <p
                      v-for="field in match.fields || []"
                      :key="field.field + field.value"
                      class="text-body-medium"
                    >
                      Related {{ field.field }}: {{ field.value }}
                    </p>
                    <p v-if="!match.fields?.length && match.found_in" class="text-body-medium">
                      {{ match.found_in }}
                    </p>
                    <p v-if="match.signal" class="text-body-medium">{{ match.signal }}</p>
                  </div>
                  <v-btn
                    color="primary"
                    variant="text"
                    size="small"
                    append-icon="mdi-chevron-right"
                    @click="viewEntity(match)"
                  >
                    View Entity
                  </v-btn>
                </div>
              </v-card-text>
            </v-card>
          </div>
        </v-card-text>
      </v-card>

      <v-alert
        v-else-if="resultItem.data?.notice_type === 'skipped_reference'"
        type="warning"
        variant="tonal"
      >
        {{ resultItem.data.message }} Case #{{ resultItem.data.case_id }}, Entity #{{
          resultItem.data.entity_id
        }}, {{ resultItem.data.field }}
      </v-alert>

      <!-- Error Message -->
      <v-alert v-else-if="resultItem.type === 'error'" border="start" elevation="1" type="error">
        {{ resultItem.data.message }}
      </v-alert>

      <!-- Completion Message -->
      <v-alert
        v-else-if="resultItem.type === 'complete' && !hasErrors"
        type="success"
        density="comfortable"
        variant="tonal"
      >
        {{
          hasWarnings
            ? 'Correlation scan completed with skipped references; reference coverage is incomplete.'
            : hasCorrelations
              ? 'Correlation scan complete'
              : 'Correlation scan complete. No correlations are available in accessible Cases.'
        }}
      </v-alert>
    </template>

    <!-- No Results -->
    <v-card v-if="!result || normalizedResult.length === 0" elevation="1" rounded="lg">
      <v-card-text class="text-center pa-8">
        <v-icon icon="mdi-magnify" size="48" color="grey-darken-1" class="mb-3" />
        <p class="text-body-medium text-medium-emphasis">
          No correlations are available in accessible Cases.
        </p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { assembleCorrelationResults } from '@/utils/correlationResults'
import { useRouter } from 'vue-router'

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  },
})

const router = useRouter()

const normalizedResult = computed(() => assembleCorrelationResults(props.result))

const latestProgress = computed(() => {
  if (normalizedResult.value.some((item) => ['complete', 'error'].includes(item.type))) return null
  return normalizedResult.value.findLast((item) => item.type === 'status')?.data || null
})

const hasErrors = computed(() => normalizedResult.value.some((item) => item.type === 'error'))

const isGroup = (item) => item.type === 'data' && Array.isArray(item.data?.matches)
const hasCorrelations = computed(() => normalizedResult.value.some(isGroup))
const hasWarnings = computed(() =>
  normalizedResult.value.some((item) => item.data?.notice_type === 'skipped_reference'),
)
const entityLabel = (entity) =>
  entity.entity_name?.trim() ||
  entity.person_name?.trim() ||
  `${entity.entity_type || 'Entity'} #${entity.entity_id}`
const resultKey = (item) => {
  const data = item.data || {}
  return isGroup(item)
    ? `${data.case_id}:${data.entity_id}:${data.match_type}:${data.normalized_value || data.matched_value || data.domain || data.employer_name || ''}`
    : `${item.type}:${data.notice_type || ''}:${data.case_id || ''}:${data.entity_id || ''}:${data.field || ''}`
}
const counts = computed(() => {
  const groups = normalizedResult.value.filter(isGroup).map((item) => item.data)
  return {
    entities: new Set(groups.map((group) => group.entity_id)).size,
    matches: groups.reduce((total, group) => total + group.matches.length, 0),
    cases: new Set(groups.flatMap((group) => group.matches.map((match) => match.case_id))).size,
  }
})

const getMatchTypeLabel = (matchType) => {
  const labels = {
    name: 'Name Match',
    employer: 'Employer Match',
    domain: 'Domain Match',
    vin: 'VIN Match',
    email: 'Email Match',
    phone: 'Phone Match',
    ip_address: 'IP Address Match',
    exact_profile: 'Exact Profile Reference',
    license_plate: 'License Plate Match',
  }
  return labels[matchType] || 'Match'
}

const getMatchTypeColor = (matchType) => {
  const colors = {
    name: 'success',
    employer: 'secondary',
    domain: 'info',
    vin: 'warning',
    email: 'success',
    phone: 'success',
    ip_address: 'success',
    exact_profile: 'success',
    license_plate: 'warning',
  }
  return colors[matchType] || 'grey'
}

const viewEntity = (match) => {
  // Navigate to the case with entity query parameter
  router.push({
    path: `/case/${match.case_id}`,
    query: { entity: match.entity_id },
  })
}
</script>
