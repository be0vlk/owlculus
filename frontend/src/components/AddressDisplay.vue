<template>
    <div v-if="address" class="mt-6">
      <h4 class="text-md font-medium text-gray-900 dark:text-white">Address</h4>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <BaseDisplayField label="Street" :value="address.street" />
        </div>
        <BaseDisplayField label="City" :value="address.city" />
        <BaseDisplayField label="State" :value="address.state" />
        <BaseDisplayField label="Country" :value="address.country" />
        <BaseDisplayField label="Postal Code" :value="address.postal_code" />
      </div>
    </div>
  </template>
  
  <script setup>
  import BaseDisplayField from './BaseDisplayField.vue';
  
  defineProps({
    address: { type: Object, default: null },
  });
  </script>