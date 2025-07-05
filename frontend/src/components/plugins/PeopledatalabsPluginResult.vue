<template>
  <div class="d-flex flex-column ga-4">
    <!-- Status Messages -->
    <PluginStatusAlert
      v-for="(item, index) in statusMessages"
      :key="`status-${index}`"
      type="status"
      :message="item.data.message"
    />

    <template v-for="(item, index) in parsedResults" :key="index">
      <!-- Person Results -->
      <v-card
        v-if="item.type === 'data' && item.data.search_type === 'person'"
        elevation="2"
        rounded="lg"
      >
        <v-card-title class="d-flex align-center justify-space-between">
          <div class="d-flex align-center">
            <v-icon icon="mdi-account" class="mr-2" />
            {{ item.data.person?.full_name || 'Person Profile' }}
          </div>
          <v-chip :color="getConfidenceColor(item.data.confidence)" size="small" variant="outlined">
            {{ item.data.confidence || 'Unknown' }} confidence
          </v-chip>
        </v-card-title>

        <v-card-text>
          <div class="d-flex flex-column ga-2">
            <!-- Basic Information -->
            <div class="d-flex align-center ga-2" v-if="item.data.person?.location_name">
              <v-icon icon="mdi-map-marker" size="small" />
              <span class="text-body-2">{{ item.data.person.location_name }}</span>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(item.data.person.location_name)"
                class="ml-auto"
              >
                <v-tooltip activator="parent" location="top">Copy location</v-tooltip>
              </v-btn>
            </div>

            <div class="d-flex align-center ga-2" v-if="item.data.person?.job_title">
              <v-icon icon="mdi-briefcase" size="small" />
              <span class="text-body-2">{{ item.data.person.job_title }}</span>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(item.data.person.job_title)"
                class="ml-auto"
              >
                <v-tooltip activator="parent" location="top">Copy job title</v-tooltip>
              </v-btn>
            </div>

            <div class="d-flex align-center ga-2" v-if="item.data.person?.job_company_name">
              <v-icon icon="mdi-domain" size="small" />
              <span class="text-body-2">{{ item.data.person.job_company_name }}</span>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(item.data.person.job_company_name)"
                class="ml-auto"
              >
                <v-tooltip activator="parent" location="top">Copy company</v-tooltip>
              </v-btn>
            </div>

            <!-- Contact Information -->
            <div v-if="item.data.person?.emails?.length">
              <div
                v-for="email in item.data.person.emails.slice(0, 3)"
                :key="email"
                class="d-flex align-center ga-2"
              >
                <v-icon icon="mdi-email" size="small" />
                <span class="text-body-2">{{ email }}</span>
                <v-btn
                  icon="mdi-content-copy"
                  size="x-small"
                  variant="text"
                  @click="copyToClipboard(email)"
                  class="ml-auto"
                >
                  <v-tooltip activator="parent" location="top">Copy email</v-tooltip>
                </v-btn>
              </div>
            </div>

            <div v-if="item.data.person?.phone_numbers?.length">
              <div
                v-for="phone in item.data.person.phone_numbers.slice(0, 2)"
                :key="phone"
                class="d-flex align-center ga-2"
              >
                <v-icon icon="mdi-phone" size="small" />
                <span class="text-body-2">{{ phone }}</span>
                <v-btn
                  icon="mdi-content-copy"
                  size="x-small"
                  variant="text"
                  @click="copyToClipboard(phone)"
                  class="ml-auto"
                >
                  <v-tooltip activator="parent" location="top">Copy phone</v-tooltip>
                </v-btn>
              </div>
            </div>

            <!-- Social Profiles -->
            <div v-if="item.data.person?.linkedin_url" class="d-flex align-center ga-2">
              <v-icon icon="mdi-linkedin" size="small" />
              <a
                :href="item.data.person.linkedin_url"
                class="text-decoration-none text-body-2"
                target="_blank"
              >
                LinkedIn Profile
              </a>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(item.data.person.linkedin_url)"
                class="ml-auto"
              >
                <v-tooltip activator="parent" location="top">Copy LinkedIn URL</v-tooltip>
              </v-btn>
            </div>

            <!-- Education Summary -->
            <div v-if="item.data.person?.education?.length" class="d-flex align-center ga-2">
              <v-icon icon="mdi-school" size="small" />
              <span class="text-body-2">{{
                item.data.person.education[0].school?.name || 'Education available'
              }}</span>
              <v-chip size="x-small" variant="outlined">
                +{{ item.data.person.education.length - 1 }} more
              </v-chip>
            </div>

            <!-- Work Experience Summary -->
            <div v-if="item.data.person?.experience?.length" class="d-flex align-center ga-2">
              <v-icon icon="mdi-briefcase-variant" size="small" />
              <span class="text-body-2"
                >{{ item.data.person.experience.length }} work
                {{ item.data.person.experience.length === 1 ? 'experience' : 'experiences' }}</span
              >
            </div>

            <!-- API Usage -->
            <div
              class="d-flex justify-space-between align-center text-caption text-medium-emphasis mt-2"
            >
              <span>API Credits: {{ item.data.api_credits_used || 1 }}</span>
              <span>People Data Labs</span>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Company Results -->
      <v-card
        v-else-if="item.type === 'data' && item.data.search_type === 'company'"
        elevation="2"
        rounded="lg"
      >
        <v-card-title class="d-flex align-center justify-space-between">
          <div class="d-flex align-center">
            <v-icon icon="mdi-domain" class="mr-2" />
            {{ item.data.company?.name || 'Company Profile' }}
          </div>
          <v-chip :color="getConfidenceColor(item.data.confidence)" size="small" variant="outlined">
            {{ item.data.confidence || 'Unknown' }} confidence
          </v-chip>
        </v-card-title>

        <v-card-text>
          <div class="d-flex flex-column ga-2">
            <!-- Basic Company Information -->
            <div class="d-flex align-center ga-2" v-if="item.data.company?.website">
              <v-icon icon="mdi-web" size="small" />
              <a
                :href="`https://${item.data.company.website}`"
                class="text-decoration-none text-body-2"
                target="_blank"
              >
                {{ item.data.company.website }}
              </a>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(item.data.company.website)"
                class="ml-auto"
              >
                <v-tooltip activator="parent" location="top">Copy website</v-tooltip>
              </v-btn>
            </div>

            <div class="d-flex align-center ga-2" v-if="item.data.company?.industry">
              <v-icon icon="mdi-factory" size="small" />
              <span class="text-body-2">{{ item.data.company.industry }}</span>
            </div>

            <div class="d-flex align-center ga-2" v-if="item.data.company?.size">
              <v-icon icon="mdi-account-group" size="small" />
              <span class="text-body-2">{{ item.data.company.size }}</span>
            </div>

            <div class="d-flex align-center ga-2" v-if="item.data.company?.founded">
              <v-icon icon="mdi-calendar" size="small" />
              <span class="text-body-2">Founded {{ item.data.company.founded }}</span>
            </div>

            <div class="d-flex align-center ga-2" v-if="item.data.company?.employee_count">
              <v-icon icon="mdi-account-multiple" size="small" />
              <span class="text-body-2">{{ item.data.company.employee_count }} employees</span>
            </div>

            <!-- Location Information -->
            <div class="d-flex align-center ga-2" v-if="item.data.company?.location_name">
              <v-icon icon="mdi-map-marker" size="small" />
              <span class="text-body-2">{{ item.data.company.location_name }}</span>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(item.data.company.location_name)"
                class="ml-auto"
              >
                <v-tooltip activator="parent" location="top">Copy location</v-tooltip>
              </v-btn>
            </div>

            <!-- Social Profiles -->
            <div v-if="item.data.company?.linkedin_url" class="d-flex align-center ga-2">
              <v-icon icon="mdi-linkedin" size="small" />
              <a
                :href="item.data.company.linkedin_url"
                class="text-decoration-none text-body-2"
                target="_blank"
              >
                LinkedIn Profile
              </a>
              <v-btn
                icon="mdi-content-copy"
                size="x-small"
                variant="text"
                @click="copyToClipboard(item.data.company.linkedin_url)"
                class="ml-auto"
              >
                <v-tooltip activator="parent" location="top">Copy LinkedIn URL</v-tooltip>
              </v-btn>
            </div>

            <!-- Technologies -->
            <div v-if="item.data.company?.technologies?.length" class="d-flex align-center ga-2">
              <v-icon icon="mdi-code-tags" size="small" />
              <span class="text-body-2"
                >{{ item.data.company.technologies.length }} technologies</span
              >
              <div class="d-flex flex-wrap ga-1 ml-2">
                <v-chip
                  v-for="tech in item.data.company.technologies.slice(0, 3)"
                  :key="tech.name"
                  size="x-small"
                  variant="outlined"
                >
                  {{ tech.name }}
                </v-chip>
                <v-chip
                  v-if="item.data.company.technologies.length > 3"
                  size="x-small"
                  variant="outlined"
                >
                  +{{ item.data.company.technologies.length - 3 }} more
                </v-chip>
              </div>
            </div>

            <!-- API Usage -->
            <div
              class="d-flex justify-space-between align-center text-caption text-medium-emphasis mt-2"
            >
              <span>API Credits: {{ item.data.api_credits_used || 1 }}</span>
              <span>People Data Labs</span>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Error Messages -->
      <v-alert v-else-if="item.type === 'error'" prominent type="error" variant="tonal">
        <template #title>
          <div class="d-flex align-center">
            <v-icon icon="mdi-alert-circle" class="mr-2" />
            Search Error
          </div>
        </template>
        <div class="text-body-1">{{ item.data.message }}</div>
      </v-alert>
    </template>

    <!-- No Results -->
    <NoResultsCard v-if="!parsedResults.length" />
  </div>
</template>

<script setup>
import { toRef } from 'vue'
import { usePluginResults } from '@/composables/usePluginResults'
import PluginStatusAlert from './PluginStatusAlert.vue'
import NoResultsCard from './NoResultsCard.vue'

const props = defineProps({
  result: {
    type: [Object, Array],
    required: true,
  },
})

const { parsedResults, statusMessages } = usePluginResults(toRef(props, 'result'))

// Helper function to get confidence color
const getConfidenceColor = (confidence) => {
  if (!confidence || confidence === 'unknown') return 'grey'

  const conf = confidence.toString().toLowerCase()
  if (conf.includes('high') || conf === '5' || conf === '4') return 'success'
  if (conf.includes('medium') || conf === '3') return 'warning'
  if (conf.includes('low') || conf === '2' || conf === '1') return 'error'

  return 'info'
}

// Copy to clipboard function
const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch (err) {
    console.error('Failed to copy text:', err)
  }
}
</script>
