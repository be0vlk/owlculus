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

      <!-- DNS Results -->
      <v-card v-else-if="item.type === 'data'" elevation="2" rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon :icon="item.data.target_type === 'ip_address' ? 'mdi-ip-network' : 'mdi-web'" class="mr-2" />
          {{ item.data.target }}
        </v-card-title>

        <v-card-text>
          <div class="d-flex flex-column ga-3">
            <!-- Record Results -->
            <div 
              v-for="(recordResult, rIndex) in item.data.results" 
              :key="rIndex"
              class="record-result"
            >
              <!-- Success Result -->
              <div v-if="recordResult.records">
                <div class="d-flex align-center mb-2">
                  <v-chip 
                    size="small" 
                    color="primary"
                    variant="tonal"
                    class="mr-2"
                  >
                    {{ recordResult.type }}{{ recordResult.ip_address ? ' (Reverse)' : '' }}
                  </v-chip>
                </div>
                
                <v-card elevation="1" rounded="lg">
                  <v-card-text>
                    <div class="d-flex justify-space-between align-start">
                      <pre class="text-body-2 font-mono flex-grow-1">{{ recordResult.records.join('\n') }}</pre>
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
                variant="outlined"
              >
                <div class="text-caption">{{ recordResult.type }} Query Failed</div>
                {{ recordResult.error }}
              </v-alert>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Completion Message -->
      <v-alert 
        v-else-if="item.type === 'complete'"
        type="success"
        density="comfortable"
        variant="tonal"
      >
        <div>{{ item.data.message }}</div>
        <div v-if="item.data.cache_entries" class="text-caption">
          Cache entries: {{ item.data.cache_entries }}
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
</style>