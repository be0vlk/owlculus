<template>
  <div class="d-flex flex-column ga-4">
    <template v-for="(item, index) in parsedResults" :key="index">
      <!-- Data Results -->
      <v-card v-if="item.type === 'data'" elevation="2" rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-web" class="mr-2" />
          {{ item.data.domain || 'Whois Results' }}
          
          <!-- Expiration warning badge -->
          <v-chip
            v-if="item.data.expiration_warning"
            color="warning"
            size="small"
            class="ml-2"
          >
            <v-icon start icon="mdi-alert" />
            Expires Soon
          </v-chip>
        </v-card-title>
        
        <v-card-text>
          <!-- Basic Registration Info -->
          <div class="mb-4">
            <h4 class="text-subtitle1 mb-2">Registration Information</h4>
            <v-row dense>
              <v-col v-if="item.data.registrar" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-domain</v-icon>
                  <div>
                    <span class="text-caption text-medium-emphasis">Registrar</span>
                    <div class="text-body-2">{{ item.data.registrar }}</div>
                  </div>
                </div>
              </v-col>
              
              <v-col v-if="item.data.org" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-office-building</v-icon>
                  <div>
                    <span class="text-caption text-medium-emphasis">Organization</span>
                    <div class="text-body-2">{{ item.data.org }}</div>
                  </div>
                </div>
              </v-col>
              
              <v-col v-if="item.data.registrant_name" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-account</v-icon>
                  <div>
                    <span class="text-caption text-medium-emphasis">Registrant</span>
                    <div class="text-body-2">{{ item.data.registrant_name }}</div>
                  </div>
                </div>
              </v-col>
              
              <v-col v-if="item.data.registrant_country" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-flag</v-icon>
                  <div>
                    <span class="text-caption text-medium-emphasis">Country</span>
                    <div class="text-body-2">{{ item.data.registrant_country }}</div>
                  </div>
                </div>
              </v-col>
            </v-row>
          </div>

          <!-- Important Dates -->
          <div class="mb-4">
            <h4 class="text-subtitle1 mb-2">Important Dates</h4>
            <v-row dense>
              <v-col v-if="item.data.creation_date" cols="12" md="4">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2" color="green">mdi-calendar-plus</v-icon>
                  <div>
                    <span class="text-caption text-medium-emphasis">Created</span>
                    <div class="text-body-2">{{ formatDate(item.data.creation_date) }}</div>
                  </div>
                </div>
              </v-col>
              
              <v-col v-if="item.data.updated_date" cols="12" md="4">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2" color="blue">mdi-calendar-edit</v-icon>
                  <div>
                    <span class="text-caption text-medium-emphasis">Updated</span>
                    <div class="text-body-2">{{ formatDate(item.data.updated_date) }}</div>
                  </div>
                </div>
              </v-col>
              
              <v-col v-if="item.data.expiration_date" cols="12" md="4">
                <div class="d-flex align-center">
                  <v-icon 
                    size="small" 
                    class="mr-2" 
                    :color="item.data.days_until_expiration < 30 ? 'error' : 'orange'"
                  >
                    mdi-calendar-remove
                  </v-icon>
                  <div>
                    <span class="text-caption text-medium-emphasis">Expires</span>
                    <div class="text-body-2">{{ formatDate(item.data.expiration_date) }}</div>
                  </div>
                </div>
              </v-col>
              
              <v-col v-if="item.data.domain_age_years" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-clock-outline</v-icon>
                  <div>
                    <span class="text-caption text-medium-emphasis">Domain Age</span>
                    <div class="text-body-2">{{ item.data.domain_age_years }} years</div>
                  </div>
                </div>
              </v-col>
              
              <v-col v-if="item.data.days_until_expiration" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon 
                    size="small" 
                    class="mr-2" 
                    :color="item.data.days_until_expiration < 30 ? 'error' : 'success'"
                  >
                    mdi-timer-outline
                  </v-icon>
                  <div>
                    <span class="text-caption text-medium-emphasis">Days Until Expiration</span>
                    <div class="text-body-2">{{ item.data.days_until_expiration }} days</div>
                  </div>
                </div>
              </v-col>
            </v-row>
          </div>

          <!-- Technical Information -->
          <div v-if="item.data.name_servers && item.data.name_servers.length" class="mb-4">
            <h4 class="text-subtitle1 mb-2">Name Servers</h4>
            <v-chip-group>
              <v-chip 
                v-for="ns in item.data.name_servers" 
                :key="ns"
                size="small"
                variant="outlined"
                @click="copyToClipboard(ns)"
              >
                <v-icon start size="small">mdi-dns</v-icon>
                {{ ns }}
              </v-chip>
            </v-chip-group>
          </div>

          <!-- Status Information -->
          <div v-if="item.data.status && item.data.status.length" class="mb-4">
            <h4 class="text-subtitle1 mb-2">Status</h4>
            <v-chip-group>
              <v-chip 
                v-for="status in item.data.status" 
                :key="status"
                size="small"
                color="blue"
                variant="tonal"
              >
                {{ status }}
              </v-chip>
            </v-chip-group>
          </div>

          <!-- Contact Information -->
          <div v-if="item.data.emails && item.data.emails.length" class="mb-4">
            <h4 class="text-subtitle1 mb-2">Contact Emails</h4>
            <v-chip-group>
              <v-chip 
                v-for="email in item.data.emails" 
                :key="email"
                size="small"
                variant="outlined"
                @click="copyToClipboard(email)"
              >
                <v-icon start size="small">mdi-email</v-icon>
                {{ email }}
              </v-chip>
            </v-chip-group>
          </div>

          <!-- Additional Technical Details -->
          <v-expansion-panels v-if="hasAdditionalDetails(item.data)" class="mt-3">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <span class="text-subtitle2">Additional Details</span>
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-row dense>
                  <v-col v-if="item.data.whois_server" cols="12" md="6">
                    <div>
                      <span class="text-caption text-medium-emphasis">Whois Server</span>
                      <div class="text-body-2">{{ item.data.whois_server }}</div>
                    </div>
                  </v-col>
                  
                  <v-col v-if="item.data.dnssec" cols="12" md="6">
                    <div>
                      <span class="text-caption text-medium-emphasis">DNSSEC</span>
                      <div class="text-body-2">{{ item.data.dnssec }}</div>
                    </div>
                  </v-col>
                  
                  <v-col v-if="item.data.admin_email" cols="12" md="6">
                    <div>
                      <span class="text-caption text-medium-emphasis">Admin Email</span>
                      <div class="text-body-2">{{ item.data.admin_email }}</div>
                    </div>
                  </v-col>
                  
                  <v-col v-if="item.data.tech_email" cols="12" md="6">
                    <div>
                      <span class="text-caption text-medium-emphasis">Tech Email</span>
                      <div class="text-body-2">{{ item.data.tech_email }}</div>
                    </div>
                  </v-col>
                </v-row>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <!-- Copy domain button -->
          <div class="d-flex align-center mt-4">
            <v-btn
              variant="outlined"
              size="small"
              @click="copyToClipboard(item.data.domain)"
            >
              <v-icon start>mdi-content-copy</v-icon>
              Copy Domain
            </v-btn>
            
            <v-btn
              v-if="item.data.emails && item.data.emails.length"
              variant="outlined"
              size="small"
              class="ml-2"
              @click="copyToClipboard(item.data.emails.join(', '))"
            >
              <v-icon start>mdi-email</v-icon>
              Copy Emails
            </v-btn>
          </div>
        </v-card-text>
      </v-card>

      <!-- Error Messages -->
      <v-alert
        v-else-if="item.type === 'error'"
        type="error"
        variant="outlined"
      >
        {{ item.data.message }}
      </v-alert>
    </template>

    <!-- No Results -->
    <v-card v-if="!parsedResults.length" elevation="2" rounded="lg">
      <v-card-text class="text-center pa-8">
        <v-icon icon="mdi-web" size="48" color="grey-darken-1" class="mb-3" />
        <p class="text-body-2 text-medium-emphasis">
          No whois results available.
        </p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  }
})

// Parse streaming results
const parsedResults = computed(() => {
  if (!props.result) return []
  
  if (Array.isArray(props.result)) {
    return props.result
  }
  
  if (props.result.type) {
    return [props.result]
  }
  
  return []
})

const formatDate = (dateString) => {
  if (!dateString) return 'Unknown'
  
  try {
    // If it's already formatted, return as is
    if (dateString.includes('UTC')) {
      return dateString
    }
    
    // Try to parse and format
    const date = new Date(dateString)
    if (isNaN(date.getTime())) {
      return dateString
    }
    
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      timeZone: 'UTC'
    })
  } catch {
    return dateString
  }
}

const hasAdditionalDetails = (data) => {
  return data.whois_server || data.dnssec || data.admin_email || data.tech_email
}

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}
</script>