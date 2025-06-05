<template>
  <div class="d-flex flex-column ga-4">
    <!-- Status Messages -->
    <template v-for="(item, index) in parsedResults" :key="`status-${index}`">
      <v-alert 
        v-if="item.type === 'status'"
        type="info"
        density="compact"
        variant="tonal"
      >
        {{ item.data.message }}
      </v-alert>
    </template>

    <!-- DNS Results Grid -->
    <div v-if="dnsResults.length" class="dns-results-grid">
      <v-row>
        <v-col 
          v-for="(dnsData, index) in dnsResults" 
          :key="`dns-${index}`"
          cols="12"
          lg="6"
        >
          <v-card elevation="2" rounded="lg" class="h-100 target-card">
            <v-card-title class="d-flex align-center bg-primary-lighten-5">
              <v-icon :icon="dnsData.target_type === 'ip_address' ? 'mdi-ip-network' : 'mdi-web'" class="mr-3" />
              <div class="flex-grow-1">
                <div class="text-h6">{{ dnsData.target }}</div>
                <div class="text-caption text-medium-emphasis">
                  {{ dnsData.target_type === 'ip_address' ? 'IP Address' : 'Domain' }}
                </div>
              </div>
            </v-card-title>

            <v-card-text class="pa-0">
              <!-- Record Results Grid -->
              <div class="pa-4">
                <div class="d-flex flex-column ga-3">
                  <div 
                    v-for="(recordResult, rIndex) in dnsData.results" 
                    :key="rIndex"
                    class="record-result"
                  >
                    <!-- Success Result -->
                    <div v-if="recordResult.records" class="mb-3">
                      <div class="d-flex align-center mb-2">
                        <v-chip 
                          size="small" 
                          color="success"
                          variant="tonal"
                          class="mr-2"
                        >
                          <v-icon icon="mdi-check-circle" size="x-small" class="mr-1" />
                          {{ recordResult.type }}{{ recordResult.ip_address ? ' (Reverse)' : '' }}
                        </v-chip>
                        <span class="text-caption text-success">{{ recordResult.records.length }} record(s)</span>
                      </div>
                      
                      <v-card elevation="1" rounded="lg" color="success-lighten-5">
                        <v-card-text class="pa-3">
                          <div class="d-flex justify-space-between align-start">
                            <pre class="text-body-2 font-mono flex-grow-1 records-display">{{ recordResult.records.join('\n') }}</pre>
                            <v-btn
                              icon="mdi-content-copy"
                              size="small"
                              variant="text"
                              @click="copyToClipboard(recordResult.records.join('\n'))"
                              class="ml-3 flex-shrink-0"
                            >
                              <v-tooltip activator="parent" location="top">Copy records</v-tooltip>
                            </v-btn>
                          </div>
                        </v-card-text>
                      </v-card>
                    </div>

                    <!-- Error Result -->
                    <v-alert 
                      v-else-if="recordResult.error"
                      type="error"
                      density="compact"
                      variant="tonal"
                      class="mb-3"
                    >
                      <template #title>
                        <div class="d-flex align-center">
                          <v-chip size="x-small" color="error" variant="text" class="mr-2">
                            {{ recordResult.type }}
                          </v-chip>
                          Query Failed
                        </div>
                      </template>
                      {{ recordResult.error }}
                    </v-alert>
                  </div>
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </div>

    <!-- Completion and Error Messages -->
    <template v-for="(item, index) in parsedResults" :key="`message-${index}`">
      <!-- Completion Message -->
      <v-alert 
        v-if="item.type === 'complete'"
        type="success"
        variant="tonal"
        class="mb-4"
      >
        <template #title>
          <div class="d-flex align-center">
            <v-icon icon="mdi-check-circle" class="mr-2" />
            DNS Lookup Complete
          </div>
        </template>
        <div class="text-body-1">{{ item.data.message }}</div>
        <div v-if="item.data.cache_entries" class="text-caption mt-2">
          Cache entries: {{ item.data.cache_entries }}
        </div>
      </v-alert>

      <!-- Error Messages -->
      <v-alert
        v-else-if="item.type === 'error'"
        type="error"
        variant="tonal"
        prominent
      >
        <template #title>
          <div class="d-flex align-center">
            <v-icon icon="mdi-alert-circle" class="mr-2" />
            DNS Lookup Error
          </div>
        </template>
        <div class="text-body-1">{{ item.data.message }}</div>
      </v-alert>
    </template>

    <!-- Legacy Format Support (for old responses) -->
    <template v-if="legacyFormat">
      <v-card elevation="2" rounded="lg">
        <v-card-text>
          <div class="d-flex align-center">
            <v-icon icon="mdi-web" class="mr-2" color="grey-darken-1" />
            <h3 class="text-h6 font-weight-medium">
              {{ legacyResult.domain }}
            </h3>
          </div>
        </v-card-text>
      </v-card>

      <div v-if="hasIpAddresses(legacyResult)">
        <h4 class="text-body-1 font-weight-medium d-flex align-center mb-2">
          <v-icon icon="mdi-map-marker-outline" class="mr-1" size="16" />
          IP Addresses
        </h4>
        <v-card elevation="1" rounded="lg">
          <v-card-text>
            <div class="d-flex justify-space-between align-start">
              <code class="text-body-2 font-mono flex-grow-1">{{ legacyResult.ips.join('\n') }}</code>
              <v-btn
                icon="mdi-content-copy"
                size="small"
                variant="text"
                @click="copyToClipboard(legacyResult.ips.join('\n'))"
                class="ml-3 flex-shrink-0"
              >
                <v-tooltip activator="parent" location="top">Copy all IP addresses</v-tooltip>
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </div>
    </template>

    <!-- No Results -->
    <v-card v-if="!parsedResults.length && !legacyFormat" elevation="2" rounded="lg">
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

// Check for legacy format (old plugin response)
const legacyFormat = computed(() => {
  return props.result && 
         !props.result.type && 
         (props.result.domain || props.result.ips);
});

const legacyResult = computed(() => {
  return legacyFormat.value ? props.result : null;
});

// Extract DNS data results
const dnsResults = computed(() => {
  return parsedResults.value
    .filter(item => item.type === 'data')
    .map(item => item.data);
});

const hasIpAddresses = (result) => {
  return result && 
         !result.error &&
         Array.isArray(result.ips) && 
         result.ips.length > 0;
};

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    console.error('Failed to copy text:', err);
  }
};
</script>

<style scoped>
.record-result {
  position: relative;
}

pre {
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.dns-results-grid {
  margin-top: 1.5rem;
}

.target-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.target-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
}

.records-display {
  max-height: 200px;
  overflow-y: auto;
  background: rgba(var(--v-theme-surface), 0.7);
  border-radius: 4px;
  padding: 8px;
  margin: 0;
}

/* Enhanced visual hierarchy for record types */
.v-chip[color="success"] {
  background: rgba(var(--v-theme-success), 0.12);
  border: 1px solid rgba(var(--v-theme-success), 0.3);
}

.bg-primary-lighten-5 {
  background: linear-gradient(45deg, rgba(var(--v-theme-primary), 0.08), rgba(var(--v-theme-primary), 0.03));
}
</style>