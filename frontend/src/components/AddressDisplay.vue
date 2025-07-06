<template>
  <v-card v-if="address" class="mt-4" variant="outlined">
    <v-card-title>
      <v-icon start>mdi-map-marker-outline</v-icon>
      Address
    </v-card-title>

    <v-card-text>
      <v-row>
        <v-col cols="12">
          <div class="mb-3">
            <v-label class="text-subtitle-2 font-weight-medium mb-1">Street</v-label>
            <div class="text-body-2 text-medium-emphasis">{{ address.street || 'N/A' }}</div>
          </div>
        </v-col>

        <v-col cols="12" sm="6">
          <div class="mb-3">
            <v-label class="text-subtitle-2 font-weight-medium mb-1">City</v-label>
            <div class="text-body-2 text-medium-emphasis">{{ address.city || 'N/A' }}</div>
          </div>
        </v-col>

        <v-col cols="12" sm="6">
          <div class="mb-3">
            <v-label class="text-subtitle-2 font-weight-medium mb-1">State</v-label>
            <div class="text-body-2 text-medium-emphasis">{{ address.state || 'N/A' }}</div>
          </div>
        </v-col>

        <v-col cols="12" sm="6">
          <div class="mb-3">
            <v-label class="text-subtitle-2 font-weight-medium mb-1">Country</v-label>
            <div class="text-body-2 text-medium-emphasis">{{ address.country || 'N/A' }}</div>
          </div>
        </v-col>

        <v-col cols="12" sm="6">
          <div class="mb-3">
            <v-label class="text-subtitle-2 font-weight-medium mb-1">Postal Code</v-label>
            <div class="text-body-2 text-medium-emphasis">{{ address.postal_code || 'N/A' }}</div>
          </div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
defineProps({
  address: { type: Object, default: null },
})
</script>
