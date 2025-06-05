<template>
  <div class="d-flex flex-column ga-4">
    <template v-for="(item, index) in parsedResults" :key="index">
      <!-- Status Messages -->
      <v-alert 
        v-if="item.type === 'status'"
        type="info"
        density="compact"
        variant="tonal"
      >
        {{ item.data.message }}
      </v-alert>

      <!-- Platform Check Result -->
      <v-card v-else-if="item.type === 'data'" elevation="2" rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon 
            :icon="item.data.exists ? 'mdi-check-circle' : 'mdi-close-circle'" 
            :color="item.data.exists ? 'success' : 'grey'"
            class="mr-2" 
          />
          {{ item.data.platform }}
          <v-spacer />
          <v-chip 
            :color="item.data.exists ? 'success' : 'grey'"
            size="small"
            variant="tonal"
          >
            {{ item.data.exists ? 'Found' : 'Not Found' }}
          </v-chip>
        </v-card-title>

        <v-card-text>
          <div class="d-flex flex-column ga-2">
            <!-- Email -->
            <div class="d-flex align-center">
              <v-icon icon="mdi-email" size="small" class="mr-2" />
              <span class="text-body-2">{{ item.data.email }}</span>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(item.data.email)"
                class="ml-2"
              >
                <v-tooltip activator="parent" location="top">Copy email</v-tooltip>
              </v-btn>
            </div>

            <!-- Domain -->
            <div v-if="item.data.domain" class="d-flex align-center">
              <v-icon icon="mdi-web" size="small" class="mr-2" />
              <span class="text-body-2">{{ item.data.domain }}</span>
            </div>

            <!-- Partial Recovery Info -->
            <div v-if="item.data.partial_info" class="d-flex align-center">
              <v-icon icon="mdi-shield-account" size="small" class="mr-2" color="warning" />
              <span class="text-body-2">Recovery: {{ item.data.partial_info }}</span>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(item.data.partial_info)"
                class="ml-2"
              >
                <v-tooltip activator="parent" location="top">Copy recovery info</v-tooltip>
              </v-btn>
            </div>

            <!-- Rate Limited -->
            <v-alert 
              v-if="item.data.ratelimited"
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
              v-if="item.data.error"
              type="error"
              density="compact"
              variant="text"
              class="mt-2"
            >
              <v-icon icon="mdi-alert" size="small" class="mr-1" />
              {{ item.data.error }}
            </v-alert>
          </div>
        </v-card-text>
      </v-card>

      <!-- Completion Message with Summary -->
      <v-alert 
        v-else-if="item.type === 'complete'"
        type="success"
        density="comfortable"
        variant="tonal"
      >
        <div class="d-flex align-center mb-2">
          <v-icon icon="mdi-check-circle" class="mr-2" />
          <span class="font-weight-medium">{{ item.data.message }}</span>
        </div>
        
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
            size="small" 
            color="warning" 
            variant="text"
          >
            <v-icon icon="mdi-clock-alert" size="small" class="mr-1" />
            {{ item.data.summary.rate_limited }} rate limited
          </v-chip>
          <v-chip 
            v-if="item.data.summary.errors > 0"
            size="small" 
            color="error" 
            variant="text"
          >
            <v-icon icon="mdi-alert" size="small" class="mr-1" />
            {{ item.data.summary.errors }} errors
          </v-chip>
        </div>

        <div v-if="item.data.timestamp" class="text-caption mt-2">
          Completed at {{ formatDate(new Date(item.data.timestamp * 1000).toISOString()) }} UTC
        </div>
      </v-alert>

      <!-- Error Messages -->
      <v-alert
        v-else-if="item.type === 'error'"
        type="error"
        variant="outlined"
      >
        {{ item.data.message }}
      </v-alert>
    </template>

    <!-- Summary Card (shown at end) -->
    <v-card 
      v-if="summaryData"
      elevation="2" 
      rounded="lg"
      color="blue-lighten-5"
    >
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-chart-box-outline" class="mr-2" />
        Results Summary
      </v-card-title>
      <v-card-text>
        <div class="d-flex flex-wrap ga-3">
          <div class="d-flex align-center">
            <v-icon icon="mdi-check-circle" color="success" size="small" class="mr-1" />
            <span class="text-body-2">
              <strong>{{ summaryData.found }}</strong> accounts found
            </span>
          </div>
          <div class="d-flex align-center">
            <v-icon icon="mdi-close-circle" color="grey" size="small" class="mr-1" />
            <span class="text-body-2">
              <strong>{{ summaryData.notFound }}</strong> not found
            </span>
          </div>
          <div v-if="summaryData.withRecoveryInfo" class="d-flex align-center">
            <v-icon icon="mdi-shield-account" color="warning" size="small" class="mr-1" />
            <span class="text-body-2">
              <strong>{{ summaryData.withRecoveryInfo }}</strong> with recovery info
            </span>
          </div>
        </div>
        
        <!-- Found Platforms List -->
        <div v-if="foundPlatforms.length" class="mt-3">
          <h4 class="text-subtitle2 mb-2">Found on platforms:</h4>
          <div class="d-flex flex-wrap ga-1">
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

    <!-- No Results -->
    <v-card v-if="!parsedResults.length" elevation="2" rounded="lg">
      <v-card-text class="text-center pa-8">
        <v-icon icon="mdi-magnify" size="48" color="grey-darken-1" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">
          No results available.
        </p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { defineProps, computed } from 'vue';
import { formatDate } from '@/composables/dateUtils';

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  }
});

// Parse streaming results
const parsedResults = computed(() => {
  if (!props.result) return [];
  
  // Handle array of results (streaming format)
  if (Array.isArray(props.result)) {
    return props.result;
  }
  
  // Handle single result with type
  if (props.result.type) {
    return [props.result];
  }
  
  return [];
});

// Extract platform data results
const platformResults = computed(() => {
  return parsedResults.value
    .filter(item => item.type === 'data')
    .map(item => item.data);
});

// Summary statistics
const summaryData = computed(() => {
  if (!platformResults.value.length) return null;
  
  const found = platformResults.value.filter(p => p.exists).length;
  const notFound = platformResults.value.filter(p => !p.exists).length;
  const withRecoveryInfo = platformResults.value.filter(p => p.partial_info).length;
  
  return {
    found,
    notFound,
    withRecoveryInfo
  };
});

// List of platforms where accounts were found
const foundPlatforms = computed(() => {
  return platformResults.value
    .filter(p => p.exists)
    .map(p => p.platform)
    .sort();
});

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    console.error('Failed to copy text:', err);
  }
};
</script>

<style scoped>
.font-mono {
  font-family: 'Courier New', monospace;
}
</style>