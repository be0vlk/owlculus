<template>
  <div>
    <!-- Basic Information -->
    <v-card variant="outlined" class="mb-4">
      <v-card-title class="text-subtitle-1">
        <v-icon start>mdi-car</v-icon>
        Vehicle Information
      </v-card-title>

      <v-card-text>
        <v-row>
          <v-col cols="12" sm="6">
            <v-text-field
              :model-value="modelValue.make"
              @update:model-value="updateField('make', $event)"
              label="Make *"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-factory"
              placeholder="Toyota"
              :rules="[requiredRule]"
              required
            />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field
              :model-value="modelValue.model"
              @update:model-value="updateField('model', $event)"
              label="Model *"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-car-info"
              placeholder="Camry"
              :rules="[requiredRule]"
              required
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-text-field
              :model-value="modelValue.year"
              @update:model-value="updateField('year', $event)"
              label="Year"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-calendar"
              type="number"
              placeholder="2024"
              :rules="[yearRule]"
            />
          </v-col>
          <v-col cols="12" sm="8">
            <v-text-field
              :model-value="modelValue.vin"
              @update:model-value="updateField('vin', $event)"
              label="VIN"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-identifier"
              placeholder="1HGCM82633A123456"
              :rules="[vinRule]"
            />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field
              :model-value="modelValue.license_plate"
              @update:model-value="updateField('license_plate', $event)"
              label="License Plate"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-card-text"
              placeholder="ABC-123"
            />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field
              :model-value="modelValue.color"
              @update:model-value="updateField('color', $event)"
              label="Color"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-palette"
              placeholder="Silver"
            />
          </v-col>
          <v-col cols="12">
            <v-text-field
              :model-value="modelValue.owner"
              @update:model-value="updateField('owner', $event)"
              label="Owner"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-account"
              placeholder="John Doe"
            />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field
              :model-value="modelValue.registration_state"
              @update:model-value="updateField('registration_state', $event)"
              label="Registration State"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-map-marker"
              placeholder="CA"
            />
          </v-col>
          <v-col cols="12">
            <v-textarea
              :model-value="modelValue.description"
              @update:model-value="updateField('description', $event)"
              label="Description (Optional)"
              variant="outlined"
              density="comfortable"
              rows="3"
              placeholder="Add any notes or context about this vehicle"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

const updateField = (field, value) => {
  emit('update:modelValue', {
    ...props.modelValue,
    [field]: value
  })
}

// Validation rules
const requiredRule = (value) => {
  return !!value || 'This field is required'
}

const yearRule = (value) => {
  if (!value) return true
  const year = parseInt(value)
  const currentYear = new Date().getFullYear()
  if (isNaN(year) || year < 1900 || year > currentYear + 1) {
    return 'Please enter a valid year'
  }
  return true
}

const vinRule = (value) => {
  if (!value) return true
  if (value.length !== 17) {
    return 'VIN must be exactly 17 characters'
  }
  if (!/^[A-HJ-NPR-Z0-9]+$/.test(value.toUpperCase())) {
    return 'VIN contains invalid characters'
  }
  return true
}
</script>