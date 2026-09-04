<template>
  <v-form ref="form" @submit.prevent="emit('submit')">
    <div v-for="(paramDef, paramName) in parameters" :key="paramName" class="mb-4">
      <!-- String/Text Parameters -->
      <v-text-field
        v-if="paramDef.type === 'string' && !paramDef.multiline"
        v-model="localValues[paramName]"
        :label="getParameterLabel(paramName, paramDef)"
        :placeholder="paramDef.description"
        :rules="getValidationRules(paramName, paramDef)"
        :required="paramDef.required"
        :error-messages="errors[paramName]"
        :aria-invalid="!!(errors[paramName] || validationErrors[paramName])"
        variant="outlined"
        density="comfortable"
        @update:model-value="handleValueChange(paramName, $event)"
        @blur="validateField(paramName)"
      >
        <template #prepend>
          <v-icon :icon="getParameterIcon(paramName, paramDef)" size="small" />
        </template>
      </v-text-field>

      <!-- Number Parameters -->
      <v-text-field
        v-else-if="paramDef.type === 'number' || paramDef.type === 'float'"
        v-model.number="localValues[paramName]"
        :label="getParameterLabel(paramName, paramDef)"
        :placeholder="paramDef.description"
        :rules="getValidationRules(paramName, paramDef)"
        :required="paramDef.required"
        :error-messages="errors[paramName]"
        :aria-invalid="!!(errors[paramName] || validationErrors[paramName])"
        type="number"
        variant="outlined"
        density="comfortable"
        @update:model-value="handleValueChange(paramName, $event)"
        @blur="validateField(paramName)"
      >
        <template #prepend>
          <v-icon :icon="getParameterIcon(paramName, paramDef)" size="small" />
        </template>
      </v-text-field>

      <!-- Boolean Parameters -->
      <v-switch
        v-else-if="paramDef.type === 'boolean'"
        v-model="localValues[paramName]"
        :label="getParameterLabel(paramName, paramDef)"
        :required="paramDef.required"
        :error-messages="errors[paramName]"
        :aria-invalid="!!(errors[paramName] || validationErrors[paramName])"
        color="primary"
        density="comfortable"
        @update:model-value="handleValueChange(paramName, $event)"
      >
        <template #prepend>
          <v-icon :icon="getParameterIcon(paramName, paramDef)" size="small" class="me-2" />
        </template>
      </v-switch>

      <!-- Select/Choice Parameters -->
      <v-select
        v-else-if="paramDef.type === 'select' && paramDef.options"
        v-model="localValues[paramName]"
        :items="paramDef.options"
        :label="getParameterLabel(paramName, paramDef)"
        :placeholder="paramDef.description"
        :rules="getValidationRules(paramName, paramDef)"
        :required="paramDef.required"
        :error-messages="errors[paramName]"
        :aria-invalid="!!(errors[paramName] || validationErrors[paramName])"
        variant="outlined"
        density="comfortable"
        @update:model-value="handleValueChange(paramName, $event)"
      >
        <template #prepend>
          <v-icon :icon="getParameterIcon(paramName, paramDef)" size="small" />
        </template>
      </v-select>

      <!-- Textarea for long text -->
      <v-textarea
        v-else-if="paramDef.type === 'text' || paramDef.multiline"
        v-model="localValues[paramName]"
        :label="getParameterLabel(paramName, paramDef)"
        :placeholder="paramDef.description"
        :rules="getValidationRules(paramName, paramDef)"
        :required="paramDef.required"
        :error-messages="errors[paramName]"
        :aria-invalid="!!(errors[paramName] || validationErrors[paramName])"
        :rows="3"
        variant="outlined"
        density="comfortable"
        @update:model-value="handleValueChange(paramName, $event)"
        @blur="validateField(paramName)"
      >
        <template #prepend>
          <v-icon :icon="getParameterIcon(paramName, paramDef)" size="small" />
        </template>
      </v-textarea>

      <!-- Fallback to text field -->
      <v-text-field
        v-else
        v-model="localValues[paramName]"
        :label="getParameterLabel(paramName, paramDef)"
        :placeholder="paramDef.description"
        :rules="getValidationRules(paramName, paramDef)"
        :required="paramDef.required"
        :error-messages="errors[paramName]"
        :aria-invalid="!!(errors[paramName] || validationErrors[paramName])"
        variant="outlined"
        density="comfortable"
        @update:model-value="handleValueChange(paramName, $event)"
        @blur="validateField(paramName)"
      >
        <template #prepend>
          <v-icon :icon="getParameterIcon(paramName, paramDef)" size="small" />
        </template>
      </v-text-field>

      <!-- Parameter Description -->
      <div v-if="paramDef.description" class="text-body-small text-medium-emphasis ml-4 mt-1">
        {{ paramDef.description }}
      </div>
    </div>
  </v-form>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  parameters: {
    type: Object,
    required: true,
  },
  modelValue: {
    type: Object,
    default: () => ({}),
  },
  errors: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['update:modelValue', 'validate', 'submit'])

// Local state
const form = ref()
const localValues = ref({})
const validationErrors = ref({})

// Initialize local values
const initializeValues = () => {
  const values = {}
  Object.keys(props.parameters).forEach((paramName) => {
    const paramDef = props.parameters[paramName]
    if (props.modelValue[paramName] !== undefined) {
      values[paramName] = props.modelValue[paramName]
    } else if (paramDef.default !== undefined) {
      values[paramName] = paramDef.default
    } else {
      // Set appropriate default based on type
      switch (paramDef.type) {
        case 'boolean':
          values[paramName] = false
          break
        case 'number':
        case 'float':
          values[paramName] = null
          break
        default:
          values[paramName] = ''
      }
    }
  })
  localValues.value = values
}

// Computed properties
const isFormValid = computed(() => {
  return Object.keys(validationErrors.value).length === 0
})

// Methods
const getParameterLabel = (paramName, paramDef) => {
  const label =
    paramDef.label || paramName.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
  return paramDef.required ? `${label} *` : label
}

const getParameterIcon = (paramName, paramDef) => {
  // Check for custom icon
  if (paramDef.icon) return paramDef.icon

  // Infer icon from parameter name or type
  const name = paramName.toLowerCase()
  if (name.includes('email')) return 'mdi-email'
  if (name.includes('domain') || name.includes('url')) return 'mdi-web'
  if (name.includes('ip') || name.includes('address')) return 'mdi-ip-network'
  if (name.includes('phone') || name.includes('mobile')) return 'mdi-phone'
  if (name.includes('name') || name.includes('user')) return 'mdi-account'
  if (name.includes('company') || name.includes('organization')) return 'mdi-office-building'
  if (name.includes('file') || name.includes('path')) return 'mdi-file'
  if (name.includes('date') || name.includes('time')) return 'mdi-calendar'
  if (paramDef.type === 'number' || paramDef.type === 'float') return 'mdi-numeric'
  if (paramDef.type === 'boolean') return 'mdi-toggle-switch'

  return 'mdi-form-textbox'
}

const isEmptyValue = (value) => value === null || value === undefined || value === ''

const getValidationRules = (paramName, paramDef) => {
  const rules = []

  // Required validation
  if (paramDef.required) {
    rules.push((value) => {
      if (paramDef.type === 'boolean') return true
      return (
        (value !== null && value !== undefined && String(value).trim() !== '') ||
        `${getParameterLabel(paramName, paramDef).replace(' *', '')} is required`
      )
    })
  }

  // Type-specific validation
  if (paramDef.type === 'email' || paramName.toLowerCase().includes('email')) {
    rules.push((value) => {
      if (isEmptyValue(value) && !paramDef.required) return true
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      return emailRegex.test(value) || 'Please enter a valid email address'
    })
  }

  if (paramDef.type === 'url' || paramName.toLowerCase().includes('url')) {
    rules.push((value) => {
      if (isEmptyValue(value) && !paramDef.required) return true
      try {
        new URL(value)
        return true
      } catch {
        return 'Please enter a valid URL'
      }
    })
  }

  if (paramDef.type === 'number' || paramDef.type === 'float') {
    rules.push((value) => {
      if (isEmptyValue(value) && !paramDef.required) return true
      const num = Number(value)
      if (isNaN(num)) return 'Please enter a valid number'
      if (paramDef.min !== undefined && num < paramDef.min) {
        return `Value must be at least ${paramDef.min}`
      }
      if (paramDef.max !== undefined && num > paramDef.max) {
        return `Value must be at most ${paramDef.max}`
      }
      return true
    })
  }

  // Length validation
  if (paramDef.minLength) {
    rules.push((value) => {
      if (isEmptyValue(value) && !paramDef.required) return true
      return (
        value.length >= paramDef.minLength || `Minimum length is ${paramDef.minLength} characters`
      )
    })
  }

  if (paramDef.maxLength) {
    rules.push((value) => {
      if (!value) return true
      return (
        value.length <= paramDef.maxLength || `Maximum length is ${paramDef.maxLength} characters`
      )
    })
  }

  // Pattern validation
  if (paramDef.pattern) {
    rules.push((value) => {
      if (isEmptyValue(value) && !paramDef.required) return true
      const regex = new RegExp(paramDef.pattern)
      return regex.test(value) || paramDef.patternMessage || 'Please enter a valid value'
    })
  }

  return rules
}

const handleValueChange = (paramName, value) => {
  localValues.value[paramName] = value
  emit('update:modelValue', { ...localValues.value })

  // Clear previous validation error for this field
  if (validationErrors.value[paramName]) {
    delete validationErrors.value[paramName]
    emitValidationState()
  }
}

const getValidationError = (name) => {
  for (const rule of getValidationRules(name, props.parameters[name])) {
    const result = rule(localValues.value[name])
    if (result !== true) return result
  }
  return null
}

const validateField = (name) => {
  const error = getValidationError(name)
  if (error) validationErrors.value[name] = error
  else delete validationErrors.value[name]
  emitValidationState()
}

const collectValidationErrors = () => {
  const errors = {}
  for (const name of Object.keys(props.parameters)) {
    const error = getValidationError(name)
    if (error) errors[name] = error
  }
  validationErrors.value = errors
  emitValidationState()
}

const validateAll = async () => {
  if (!form.value) return false
  const { valid } = await form.value.validate()
  collectValidationErrors()
  if (valid) emit('update:modelValue', { ...localValues.value })
  return valid
}

const emitValidationState = () => {
  emit('validate', isFormValid.value, validationErrors.value)
}

// Watchers
watch(
  () => props.parameters,
  () => {
    initializeValues()
  },
  { immediate: true },
)

watch(
  () => props.modelValue,
  () => {
    initializeValues()
  },
  { immediate: true },
)

// Initialize
initializeValues()
nextTick(() => {
  emitValidationState()
})

// Expose validation method
defineExpose({
  validate: validateAll,
})
</script>

<style scoped>
/* Any custom styles if needed */
</style>
