<template>
  <div class="d-flex flex-column ga-4">
    <template v-for="(item, index) in dataResults" :key="index">
      <v-card elevation="1" rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-web" class="mr-2" />
          {{ item.data.domain || 'Whois Results' }}

          <v-chip v-if="item.data.expiration_warning" class="ml-2" color="warning" size="small">
            <v-icon start icon="mdi-alert" />
            Expires Soon
          </v-chip>
        </v-card-title>

        <v-card-text>
          <div class="mb-4">
            <h4 class="text-subtitle1 mb-2">Registration Information</h4>
            <v-row density="compact">
              <v-col v-if="item.data.registrar" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-domain</v-icon>
                  <div>
                    <span class="text-body-small text-medium-emphasis">Registrar</span>
                    <div class="text-body-medium">{{ item.data.registrar }}</div>
                  </div>
                </div>
              </v-col>

              <v-col v-if="item.data.org" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-office-building</v-icon>
                  <div>
                    <span class="text-body-small text-medium-emphasis">Organization</span>
                    <div class="text-body-medium">{{ item.data.org }}</div>
                  </div>
                </div>
              </v-col>

              <v-col v-if="item.data.registrant_name" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-account</v-icon>
                  <div>
                    <span class="text-body-small text-medium-emphasis">Registrant</span>
                    <div class="text-body-medium">{{ item.data.registrant_name }}</div>
                  </div>
                </div>
              </v-col>

              <v-col v-if="item.data.registrant_country" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-flag</v-icon>
                  <div>
                    <span class="text-body-small text-medium-emphasis">Country</span>
                    <div class="text-body-medium">{{ item.data.registrant_country }}</div>
                  </div>
                </div>
              </v-col>
            </v-row>
          </div>

          <div class="mb-4">
            <h4 class="text-subtitle1 mb-2">Important Dates</h4>
            <v-row density="compact">
              <v-col v-if="item.data.creation_date" cols="12" md="4">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2" color="green">mdi-calendar-plus</v-icon>
                  <div>
                    <span class="text-body-small text-medium-emphasis">Created</span>
                    <div class="text-body-medium">
                      {{ formatResultDate(item.data.creation_date) }}
                    </div>
                  </div>
                </div>
              </v-col>

              <v-col v-if="item.data.updated_date" cols="12" md="4">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2" color="blue">mdi-calendar-edit</v-icon>
                  <div>
                    <span class="text-body-small text-medium-emphasis">Updated</span>
                    <div class="text-body-medium">
                      {{ formatResultDate(item.data.updated_date) }}
                    </div>
                  </div>
                </div>
              </v-col>

              <v-col v-if="item.data.expiration_date" cols="12" md="4">
                <div class="d-flex align-center">
                  <v-icon
                    class="mr-2"
                    size="small"
                    :color="item.data.days_until_expiration < 30 ? 'error' : 'orange'"
                  >
                    mdi-calendar-remove
                  </v-icon>
                  <div>
                    <span class="text-body-small text-medium-emphasis">Expires</span>
                    <div class="text-body-medium">
                      {{ formatResultDate(item.data.expiration_date) }}
                    </div>
                  </div>
                </div>
              </v-col>

              <v-col v-if="item.data.domain_age_years" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon size="small" class="mr-2">mdi-clock-outline</v-icon>
                  <div>
                    <span class="text-body-small text-medium-emphasis">Domain Age</span>
                    <div class="text-body-medium">{{ item.data.domain_age_years }} years</div>
                  </div>
                </div>
              </v-col>

              <v-col v-if="item.data.days_until_expiration" cols="12" md="6">
                <div class="d-flex align-center">
                  <v-icon
                    class="mr-2"
                    size="small"
                    :color="item.data.days_until_expiration < 30 ? 'error' : 'success'"
                  >
                    mdi-timer-outline
                  </v-icon>
                  <div>
                    <span class="text-body-small text-medium-emphasis">Days Until Expiration</span>
                    <div class="text-body-medium">{{ item.data.days_until_expiration }} days</div>
                  </div>
                </div>
              </v-col>
            </v-row>
          </div>

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

          <v-expansion-panels v-if="hasAdditionalDetails(item.data)" class="mt-3">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <span class="text-subtitle2">Additional Details</span>
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-row density="compact">
                  <v-col v-if="item.data.whois_server" cols="12" md="6">
                    <div>
                      <span class="text-body-small text-medium-emphasis">Whois Server</span>
                      <div class="text-body-medium">{{ item.data.whois_server }}</div>
                    </div>
                  </v-col>

                  <v-col v-if="item.data.dnssec" cols="12" md="6">
                    <div>
                      <span class="text-body-small text-medium-emphasis">DNSSEC</span>
                      <div class="text-body-medium">{{ item.data.dnssec }}</div>
                    </div>
                  </v-col>

                  <v-col v-if="item.data.admin_email" cols="12" md="6">
                    <div>
                      <span class="text-body-small text-medium-emphasis">Admin Email</span>
                      <div class="text-body-medium">{{ item.data.admin_email }}</div>
                    </div>
                  </v-col>

                  <v-col v-if="item.data.tech_email" cols="12" md="6">
                    <div>
                      <span class="text-body-small text-medium-emphasis">Tech Email</span>
                      <div class="text-body-medium">{{ item.data.tech_email }}</div>
                    </div>
                  </v-col>
                </v-row>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <div class="d-flex align-center mt-4">
            <v-btn size="small" variant="outlined" @click="copyToClipboard(item.data.domain)">
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
    </template>

    <v-alert
      v-for="(item, index) in errorMessages"
      :key="`error-${index}`"
      type="error"
      variant="outlined"
    >
      {{ item.data.message }}
    </v-alert>

    <v-card v-if="!result.length" elevation="1" rounded="lg">
      <v-card-text class="text-center pa-8">
        <v-icon icon="mdi-web" size="48" color="grey-darken-1" class="mb-3" />
        <p class="text-body-medium text-medium-emphasis">No whois results available.</p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { toRef } from 'vue'
import { copyToClipboard } from '@/utils/clipboard'
import { usePluginResults, formatResultDate } from '@/composables/usePluginResults'

const props = defineProps({
  result: {
    type: Array,
    required: true,
  },
})

const { dataResults, errorMessages } = usePluginResults(toRef(props, 'result'))

const hasAdditionalDetails = (data) => {
  return data.whois_server || data.dnssec || data.admin_email || data.tech_email
}
</script>
