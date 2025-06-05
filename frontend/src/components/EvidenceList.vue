<template>
  <div class="d-flex flex-column ga-4">
    <div v-if="loading" class="d-flex justify-center">
      <v-progress-circular
        indeterminate
        :size="50"
        :width="8"
        color="primary"
      />
    </div>
    <v-alert v-else-if="error" type="error">
      {{ error }}
    </v-alert>
    <v-card v-else elevation="1" rounded="lg">
      <div class="file-explorer">
        <template v-for="category in CATEGORIES" :key="category">
          <div class="directory-group">
            <v-list-item 
              @click="toggleDirectory(category)"
              class="cursor-pointer"
              :class="{ 'bg-surface': expandedDirectories[category] }"
            >
              <template v-slot:prepend>
                <v-icon 
                  :icon="expandedDirectories[category] ? 'mdi-chevron-down' : 'mdi-chevron-right'"
                  color="grey-darken-1"
                  class="mr-2"
                />
                <v-icon 
                  icon="mdi-folder"
                  color="grey-darken-1"
                  class="mr-2"
                />
              </template>
              
              <v-list-item-title class="font-weight-medium">
                {{ category }}
              </v-list-item-title>
              
              <template v-slot:append>
                <v-chip 
                  size="small" 
                  variant="tonal"
                  color="grey"
                >
                  {{ groupedEvidence[category]?.length || 0 }} items
                </v-chip>
              </template>
            </v-list-item>
            
            <v-expand-transition>
              <div v-if="expandedDirectories[category]" class="ml-8">
                <template v-if="groupedEvidence[category]?.length">
                  <v-list-item 
                    v-for="evidence in groupedEvidence[category]" 
                    :key="evidence.id"
                    class="evidence-item"
                  >
                    <template v-slot:prepend>
                      <v-icon 
                        v-if="evidence.evidence_type === 'file'"
                        icon="mdi-file-document"
                        color="grey-darken-1"
                        class="mr-2"
                      />
                    </template>
                    
                    <v-list-item-title class="text-body-2 font-weight-medium">
                      {{ evidence.title }}
                    </v-list-item-title>
                    
                    <v-list-item-subtitle v-if="evidence.description" class="text-caption text-medium-emphasis">
                      {{ evidence.description }}
                    </v-list-item-subtitle>
                    
                    <v-list-item-subtitle class="text-caption text-medium-emphasis">
                      Added {{ formatDate(evidence.created_at) }} UTC
                    </v-list-item-subtitle>
                    
                    <template v-slot:append>
                      <div class="d-flex ga-2">
                        <v-btn
                          v-if="evidence.evidence_type === 'file'"
                          size="small"
                          variant="outlined"
                          icon
                          @click="$emit('download', evidence)"
                        >
                          <v-icon>mdi-download</v-icon>
                          <v-tooltip activator="parent" location="top">Download</v-tooltip>
                        </v-btn>
                        <v-btn
                          size="small"
                          color="error"
                          variant="outlined"
                          icon
                          @click="$emit('delete', evidence)"
                        >
                          <v-icon>mdi-delete</v-icon>
                          <v-tooltip activator="parent" location="top">Delete</v-tooltip>
                        </v-btn>
                      </div>
                    </template>
                  </v-list-item>
                </template>
                <div v-else class="py-8 text-center">
                  <v-icon icon="mdi-inbox" size="48" color="grey-darken-1" class="mb-3" />
                  <h3 class="text-body-1 font-weight-medium mb-1">No evidence in this category</h3>
                  <p class="text-body-2 text-medium-emphasis">Upload new evidence to get started</p>
                </div>
              </div>
            </v-expand-transition>
          </div>
        </template>
      </div>
    </v-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { formatDate } from '@/composables/dateUtils';
// Vuetify components are auto-imported

const props = defineProps({
  evidenceList: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
});

const expandedDirectories = ref({});

const CATEGORIES = [
  'Social Media',
  'Associates',
  'Network Assets',
  'Communications',
  'Documents',
  'Other'
];

const groupedEvidence = computed(() => {
  const groups = {};
  
  props.evidenceList.forEach(evidence => {
    const category = evidence.category || 'Other';
    if (!groups[category]) {
      groups[category] = [];
    }
    groups[category].push(evidence);
  });

  return groups;
});

const toggleDirectory = (category) => {
  expandedDirectories.value[category] = !expandedDirectories.value[category];
};

defineEmits(['download', 'delete']);
</script>

<style scoped>
.evidence-item:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.05);
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
