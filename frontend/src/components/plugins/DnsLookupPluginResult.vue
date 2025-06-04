<template>
  <div class="d-flex flex-column ga-4">
    <template v-for="(resultItem, index) in normalizedResult" :key="index">
      <!-- Domain Header -->
      <v-card elevation="2" rounded="lg">
        <v-card-text>
          <div class="d-flex align-center">
            <v-icon icon="mdi-web" class="mr-2" color="grey-darken-1" />
            <h3 class="text-h6 font-weight-medium">
              {{ resultItem.domain }}
            </h3>
          </div>
        </v-card-text>
      </v-card>

      <!-- IP Addresses -->
      <div v-if="hasIpAddresses(resultItem)">
        <h4 class="text-body-1 font-weight-medium d-flex align-center mb-2">
          <v-icon icon="mdi-map-marker-outline" class="mr-1" size="16" />
          IP Addresses
        </h4>
        <v-card elevation="1" rounded="lg">
          <v-card-text>
            <div class="d-flex justify-space-between align-start">
              <code class="text-body-2 font-mono flex-grow-1">{{ resultItem.ips.join('\n') }}</code>
              <v-btn
                icon="mdi-content-copy"
                size="small"
                variant="text"
                @click="copyToClipboard(resultItem.ips.join('\n'))"
                class="ml-3 flex-shrink-0"
              >
                <v-tooltip activator="parent" location="top">Copy all IP addresses</v-tooltip>
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </div>

      <!-- No IP Results -->
      <v-card v-else elevation="1" rounded="lg">
        <v-card-text>
          <p class="text-body-2 text-medium-emphasis">
            No IP addresses found for this domain.
          </p>
        </v-card-text>
      </v-card>
    </template>

    <!-- No Results at all -->
    <v-card v-if="!result || normalizedResult.length === 0" elevation="2" rounded="lg">
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
// Vuetify components are auto-imported

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  }
});

const normalizedResult = computed(() => {
  if (!props.result) return [];
  return Array.isArray(props.result) ? props.result : [props.result];
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
</style>
