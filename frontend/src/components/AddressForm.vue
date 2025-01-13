<template>
    <div>
        <h4 class="text-md font-medium text-gray-900 dark:text-white mb-4">Address</h4>
        <div class="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div class="sm:col-span-2">
            <BaseInput label="Street" id="street" v-model="localAddress.street" />
          </div>
          <BaseInput label="City" id="city" v-model="localAddress.city" />
          <BaseInput label="State" id="state" v-model="localAddress.state" />
          <BaseInput label="Country" id="country" v-model="localAddress.country" />
          <BaseInput label="Postal Code" id="postalCode" v-model="localAddress.postal_code" />
        </div>
    </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import BaseInput from './BaseInput.vue'

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
