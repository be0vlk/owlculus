<template>
  <div class="d-flex flex-column ga-4">
    <template v-for="(resultItem, index) in normalizedResult" :key="index">
      <!-- Entity Match Card -->
      <v-card v-if="resultItem.type === 'data'" elevation="2" rounded="lg">
        <!-- Entity Header -->
        <v-card-text class="border-b">
          <div class="d-flex align-center">
            <v-icon icon="mdi-link" class="mr-2" color="grey-darken-1" />
            <h3 class="text-h6 font-weight-medium">
              {{ resultItem.data.entity_name }}
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
          <div class="mt-2 text-body-2 text-medium-emphasis">
            <template v-if="resultItem.data.match_type === 'employer'">
              Found multiple people who work at
              <span class="font-weight-medium">{{ resultItem.data.employer_name }}</span
              >. This employer connection may indicate a relationship between these cases.
            </template>
            <template v-else-if="resultItem.data.match_type === 'domain'">
              Found multiple entities associated with the domain
              <span class="font-weight-medium">{{ resultItem.data.domain }}</span
              >. This domain connection may indicate a relationship between these cases or entities.
            </template>
            <template v-else-if="resultItem.data.match_type === 'vin'">
              Found multiple vehicles with the same VIN
              <span class="font-weight-medium">{{ resultItem.data.matched_value }}</span
              >. This indicates the same vehicle appears in multiple cases, which strongly suggests
              a connection between these investigations.
            </template>
            <template v-else-if="resultItem.data.match_type === 'license_plate'">
              Found multiple vehicles with the same license plate
              <span class="font-weight-medium">{{ resultItem.data.matched_value }}</span
              >. This indicates the same vehicle appears in multiple cases, suggesting a connection
              between these investigations.
            </template>
            <template v-else>
              Found an entity named
              <span class="font-weight-medium">{{ resultItem.data.entity_name }}</span> that appears
              in multiple cases. This may indicate the same {{ resultItem.data.entity_type }} is
              involved in different investigations.
            </template>
          </div>
        </v-card-text>

        <!-- Matches List -->
        <v-card-text>
          <div class="d-flex flex-column ga-3">
            <v-card
              v-for="(match, matchIndex) in resultItem.data.matches"
              :key="matchIndex"
              elevation="1"
              rounded="lg"
            >
              <v-card-text>
                <div class="d-flex justify-space-between align-start">
                  <div class="d-flex flex-column ga-1">
                    <h4 class="text-body-1 font-weight-medium">Case #{{ match.case_number }}</h4>
                    <p class="text-body-2 text-medium-emphasis">
                      {{ match.case_title }}
                    </p>
                    <template v-if="resultItem.data.match_type === 'employer' && match.person_name">
                      <p class="text-body-2 text-secondary">Person: {{ match.person_name }}</p>
                    </template>
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

      <!-- Error Message -->
      <v-alert v-else-if="resultItem.type === 'error'" border="start" elevation="2" type="error">
        {{ resultItem.data.message }}
      </v-alert>

      <!-- Completion Message -->
      <v-alert
        v-else-if="resultItem.type === 'complete'"
        type="success"
        density="comfortable"
        variant="tonal"
      >
        {{ resultItem.data.message }}
      </v-alert>
    </template>

    <!-- No Results -->
    <v-card v-if="!result || normalizedResult.length === 0" elevation="2" rounded="lg">
      <v-card-text class="text-center pa-8">
        <v-icon icon="mdi-magnify" size="48" color="grey-darken-1" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">No correlations found</p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  },
})

const router = useRouter()

const normalizedResult = computed(() => {
  if (!props.result) return []
  return Array.isArray(props.result) ? props.result : [props.result]
})

const getMatchTypeLabel = (matchType) => {
  const labels = {
    name: 'Name Match',
    employer: 'Employer Match',
    domain: 'Domain Match',
    vin: 'VIN Match',
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
