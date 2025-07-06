<template>
  <div class="d-flex flex-column ga-4">
    <!-- Results Overview Card -->
    <v-card v-if="summaryData" class="results-overview" color="primary" variant="outlined">
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-chart-box-outline" class="mr-3" />
        <span>Scan Overview</span>
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" sm="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-success font-weight-bold">{{ summaryData.found }}</div>
              <div class="text-body-2">Accounts Found</div>
            </div>
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-medium-emphasis font-weight-bold">
                {{ summaryData.notFound }}
              </div>
              <div class="text-body-2">Not Found</div>
            </div>
          </v-col>
          <v-col cols="12" sm="6" md="3" v-if="summaryData.withRecoveryInfo">
            <div class="text-center">
              <div class="text-h4 text-warning font-weight-bold">
                {{ summaryData.withRecoveryInfo }}
              </div>
              <div class="text-body-2">With Recovery Info</div>
            </div>
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <div class="text-center">
              <div class="text-h4 text-primary font-weight-bold">{{ platformResults.length }}</div>
              <div class="text-body-2">Total Platforms</div>
            </div>
          </v-col>
        </v-row>

        <!-- Found Platforms Quick View -->
        <div v-if="foundPlatforms.length" class="mt-4">
          <h4 class="text-subtitle1 mb-2">Found on platforms:</h4>
          <div class="d-flex flex-wrap ga-2">
            <v-chip
              v-for="platform in foundPlatforms"
              :key="platform"
              size="small"
              color="success"
              variant="tonal"
            >
              {{ platform }}
            </v-chip>
          </div>
        </div>
      </v-card-text>
    </v-card>

    <!-- Status Messages -->
    <PluginStatusAlert
      v-for="(item, index) in statusMessages"
      :key="`status-${index}`"
      type="status"
      :message="item.data.message"
    />

    <!-- Results Grid for Platform Data -->
    <div v-if="platformResults.length" class="platform-results-grid">
      <v-row>
        <v-col
          v-for="(platformData, index) in platformResults"
          :key="`platform-${index}`"
          cols="12"
          md="6"
          lg="4"
        >
          <v-card
            elevation="2"
            rounded="lg"
            :color="platformData.exists ? 'success-lighten-5' : 'grey-lighten-4'"
            class="h-100"
          >
            <v-card-title class="d-flex align-center">
              <v-icon
                :icon="platformData.exists ? 'mdi-check-circle' : 'mdi-close-circle'"
                :color="platformData.exists ? 'success' : 'grey'"
                class="mr-2"
              />
              {{ platformData.platform }}
              <v-spacer />
              <v-chip
                :color="platformData.exists ? 'success' : 'grey'"
                size="small"
                variant="tonal"
              >
                {{ platformData.exists ? 'Found' : 'Not Found' }}
              </v-chip>
            </v-card-title>

            <v-card-text>
              <div class="d-flex flex-column ga-2">
                <!-- Email -->
                <div class="d-flex align-center">
                  <v-icon icon="mdi-email" size="small" class="mr-2" />
                  <span class="text-body-2">{{ platformData.email }}</span>
                  <v-btn
                    icon="mdi-content-copy"
                    size="x-small"
                    variant="text"
                    @click="copyToClipboard(platformData.email)"
                    class="ml-2"
                  >
                    <v-tooltip activator="parent" location="top">Copy email</v-tooltip>
                  </v-btn>
                </div>

                <!-- Domain -->
                <div v-if="platformData.domain" class="d-flex align-center">
                  <v-icon icon="mdi-web" size="small" class="mr-2" />
                  <span class="text-body-2">{{ platformData.domain }}</span>
                </div>

                <!-- Partial Recovery Info -->
                <div v-if="platformData.partial_info" class="d-flex align-center">
                  <v-icon icon="mdi-shield-account" size="small" class="mr-2" color="warning" />
                  <span class="text-body-2">Recovery: {{ platformData.partial_info }}</span>
                  <v-btn
                    icon="mdi-content-copy"
                    size="x-small"
                    variant="text"
                    @click="copyToClipboard(platformData.partial_info)"
                    class="ml-2"
                  >
                    <v-tooltip activator="parent" location="top">Copy recovery info</v-tooltip>
                  </v-btn>
                </div>

                <!-- Rate Limited -->
                <v-alert
                  v-if="platformData.ratelimited"
                  type="warning"
                  density="compact"
                  variant="text"
                  class="mt-2"
                >
                  <v-icon icon="mdi-clock-alert" size="small" class="mr-1" />
                  Rate limited - result may be incomplete
                </v-alert>

                <!-- Error -->
                <v-alert
                  v-if="platformData.error"
                  type="error"
                  density="compact"
                  variant="text"
                  class="mt-2"
                >
                  <v-icon icon="mdi-alert" size="small" class="mr-1" />
                  {{ platformData.error }}
                </v-alert>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </div>

    <!-- Completion and Error Messages -->
    <template v-for="(item, index) in parsedResults" :key="`message-${index}`">
      <!-- Completion Message -->
      <v-alert v-if="item.type === 'complete'" class="mb-4" type="success" variant="tonal">
        <template #title>
          <div class="d-flex align-center">
            <v-icon icon="mdi-check-circle" class="mr-2" />
            Scan Complete
          </div>
        </template>
        <div class="text-body-1 mb-2">{{ item.data.message }}</div>

        <div v-if="item.data.summary" class="d-flex flex-wrap ga-2">
          <v-chip size="small" color="primary" variant="text">
            <v-icon icon="mdi-web" size="small" class="mr-1" />
            {{ item.data.summary.total_platforms }} platforms
          </v-chip>
          <v-chip size="small" color="success" variant="text">
            <v-icon icon="mdi-check" size="small" class="mr-1" />
            {{ item.data.summary.accounts_found }} found
          </v-chip>
          <v-chip
            v-if="item.data.summary.rate_limited > 0"
            color="warning"
            size="small"
            variant="text"
          >
            <v-icon icon="mdi-clock-alert" size="small" class="mr-1" />
            {{ item.data.summary.rate_limited }} rate limited
          </v-chip>
          <v-chip v-if="item.data.summary.errors > 0" color="error" size="small" variant="text">
            <v-icon icon="mdi-alert" size="small" class="mr-1" />
            {{ item.data.summary.errors }} errors
          </v-chip>
        </div>

        <div v-if="item.data.timestamp" class="text-caption mt-2">
          Completed at {{ formatDate(new Date(item.data.timestamp * 1000).toISOString()) }} UTC
        </div>
      </v-alert>

      <!-- Error Messages -->
      <v-alert v-else-if="item.type === 'error'" prominent type="error" variant="tonal">
        <template #title>
          <div class="d-flex align-center">
            <v-icon icon="mdi-alert-circle" class="mr-2" />
            Scan Error
          </div>
        </template>
        <div class="text-body-1">{{ item.data.message }}</div>
      </v-alert>
    </template>

    <!-- No Results -->
    <NoResultsCard v-if="!parsedResults.length" />
  </div>
</template>

<script setup>
import { computed, toRef } from 'vue'
import { formatDate } from '@/composables/dateUtils'
import { usePluginResults } from '@/composables/usePluginResults'
import PluginStatusAlert from './PluginStatusAlert.vue'
import NoResultsCard from './NoResultsCard.vue'

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  },
})

const { parsedResults, statusMessages } = usePluginResults(toRef(props, 'result'))

// Extract platform data results
const platformResults = computed(() => {
  return parsedResults.value.filter((item) => item.type === 'data').map((item) => item.data)
})

// Summary statistics
const summaryData = computed(() => {
  if (!platformResults.value.length) return null

  const found = platformResults.value.filter((p) => p.exists).length
  const notFound = platformResults.value.filter((p) => !p.exists).length
  const withRecoveryInfo = platformResults.value.filter((p) => p.partial_info).length

  return {
    found,
    notFound,
    withRecoveryInfo,
  }
})

// List of platforms where accounts were found
const foundPlatforms = computed(() => {
  return platformResults.value
    .filter((p) => p.exists)
    .map((p) => p.platform)
    .sort()
})

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}
</script>

<style scoped>
.font-mono {
  font-family: 'Courier New', monospace;
}

.results-overview {
  background: linear-gradient(
    45deg,
    rgb(var(--v-theme-primary), 0.05),
    rgb(var(--v-theme-primary), 0.02)
  );
}

.platform-results-grid {
  margin-top: 1.5rem;
}

/* Enhanced hover effects for platform cards */
.platform-results-grid .v-card {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.platform-results-grid .v-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgb(0 0 0 / 15%);
}

/* Better visual hierarchy for found vs not found */
.v-card[style*='success-lighten-5'] {
  border-left: 4px solid rgb(var(--v-theme-success));
}

.v-card[style*='grey-lighten-4'] {
  border-left: 4px solid rgb(var(--v-theme-surface-variant));
}
</style>
