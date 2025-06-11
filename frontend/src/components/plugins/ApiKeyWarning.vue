<template>
  <v-alert
    type="warning"
    variant="tonal"
    class="mb-4"
    prominent
  >
    <v-alert-title>API Key Required</v-alert-title>
    <div>
      {{ computedMessage }}
    </div>
    <template v-if="showAdminLink && isAdmin" #append>
      <v-btn
        variant="text"
        size="small"
        color="warning"
        :to="{ name: 'admin-dashboard' }"
        append-icon="mdi-arrow-right"
      >
        Configure API Keys
      </v-btn>
    </template>
    <template v-else #append>
      <v-icon size="large">mdi-key-alert</v-icon>
    </template>
  </v-alert>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  missingProviders: {
    type: Array,
    default: () => []
  },
  showAdminLink: {
    type: Boolean,
    default: true
  }
})

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.userRole === 'Admin')

const computedMessage = computed(() => {
  if (props.missingProviders.length === 0) {
    return 'This plugin requires an API key. Contact your administrator to set it up.'
  }
  
  const providers = props.missingProviders
    .map(p => p.charAt(0).toUpperCase() + p.slice(1))
    .join(', ')
  
  const plural = props.missingProviders.length > 1
  return `This plugin requires ${plural ? 'API keys' : 'an API key'} for: ${providers}. Contact your administrator to set ${plural ? 'them' : 'it'} up.`
})
</script>