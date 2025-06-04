<template>
  <div>
    <v-card-subtitle class="text-h6 pa-0 mb-4">
      <v-icon start>mdi-map-marker-outline</v-icon>
      Address
    </v-card-subtitle>
    
    <v-row>
      <v-col cols="12">
        <v-text-field
          v-model="localAddress.street"
          label="Street"
          variant="outlined"
          density="comfortable"
        />
      </v-col>
      
      <v-col cols="12" sm="6">
        <v-text-field
          v-model="localAddress.city"
          label="City"
          variant="outlined"
          density="comfortable"
        />
      </v-col>
      
      <v-col cols="12" sm="6">
        <v-text-field
          v-model="localAddress.state"
          label="State"
          variant="outlined"
          density="comfortable"
        />
      </v-col>
      
      <v-col cols="12" sm="6">
        <v-text-field
          v-model="localAddress.country"
          label="Country"
          variant="outlined"
          density="comfortable"
        />
      </v-col>
      
      <v-col cols="12" sm="6">
        <v-text-field
          v-model="localAddress.postal_code"
          label="Postal Code"
          variant="outlined"
          density="comfortable"
        />
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits(['update:modelValue']);

const localAddress = ref({ ...props.modelValue });

watch(localAddress, () => {
  emit('update:modelValue', { ...localAddress.value });
}, { deep: true });

watch(() => props.modelValue, (newVal) => {
  localAddress.value = { ...newVal };
}, { deep: true });
</script>
