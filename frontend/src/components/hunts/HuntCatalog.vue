<template>
  <div class="hunt-catalog">
    <!-- Search and Filter Bar -->
    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <v-row align="center">
          <v-col cols="12" md="6">
            <v-text-field
              v-model="searchQuery"
              prepend-inner-icon="mdi-magnify"
              label="Search hunts..."
              variant="outlined"
              density="comfortable"
              clearable
              hide-details
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-select
              v-model="selectedCategory"
              :items="categoryOptions"
              label="Category"
              variant="outlined"
              density="comfortable"
              clearable
              hide-details
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-btn-toggle
              v-model="viewMode"
              mandatory
              variant="outlined"
              density="comfortable"
            >
              <v-btn value="grid" icon="mdi-view-grid" />
              <v-btn value="list" icon="mdi-view-list" />
            </v-btn-toggle>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Loading State -->
    <div v-if="loading" class="text-center pa-8">
      <v-progress-circular indeterminate size="64" />
      <div class="text-h6 mt-4">Loading hunts...</div>
    </div>

    <!-- Error State -->
    <v-alert v-else-if="error" type="error" class="mb-4">
      {{ error }}
      <template #append>
        <v-btn @click="$emit('retry')" variant="text" size="small">
          Retry
        </v-btn>
      </template>
    </v-alert>

    <!-- Empty State -->
    <v-card v-else-if="filteredHunts.length === 0" variant="outlined" class="text-center pa-8">
      <v-icon icon="mdi-folder-search" size="64" color="grey" class="mb-4" />
      <div class="text-h6 mb-2">No hunts found</div>
      <div class="text-body-2 text-medium-emphasis">
        {{ searchQuery || selectedCategory ? 'Try adjusting your search or filter criteria' : 'No hunt templates are available' }}
      </div>
      <v-btn
        v-if="searchQuery || selectedCategory"
        @click="clearFilters"
        color="primary"
        variant="text"
        class="mt-4"
      >
        Clear Filters
      </v-btn>
    </v-card>

    <!-- Hunt Grid/List -->
    <div v-else>
      <!-- Grid View -->
      <v-row v-if="viewMode === 'grid'">
        <v-col
          v-for="hunt in filteredHunts"
          :key="hunt.id"
          cols="12"
          sm="6"
          md="4"
          lg="3"
        >
          <HuntCard
            :hunt="hunt"
            @execute="$emit('execute', hunt)"
            @view-details="$emit('view-details', hunt)"
          />
        </v-col>
      </v-row>

      <!-- List View -->
      <div v-else class="hunt-list">
        <HuntListItem
          v-for="hunt in filteredHunts"
          :key="hunt.id"
          :hunt="hunt"
          class="mb-2"
          @execute="$emit('execute', hunt)"
          @view-details="$emit('view-details', hunt)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import HuntCard from './HuntCard.vue'
import HuntListItem from './HuntListItem.vue'

const props = defineProps({
  hunts: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['execute', 'view-details', 'retry'])

// Local state
const searchQuery = ref('')
const selectedCategory = ref(null)
const viewMode = ref('grid')

// Computed properties
const categoryOptions = computed(() => {
  const categories = [...new Set(props.hunts.map(hunt => hunt.category))]
  return categories.map(category => ({
    title: category.charAt(0).toUpperCase() + category.slice(1),
    value: category
  }))
})

const filteredHunts = computed(() => {
  let filtered = props.hunts

  // Filter by search query
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(hunt =>
      hunt.display_name.toLowerCase().includes(query) ||
      hunt.description.toLowerCase().includes(query) ||
      hunt.category.toLowerCase().includes(query)
    )
  }

  // Filter by category
  if (selectedCategory.value) {
    filtered = filtered.filter(hunt => hunt.category === selectedCategory.value)
  }

  // Sort by category, then by display name
  return filtered.sort((a, b) => {
    if (a.category !== b.category) {
      return a.category.localeCompare(b.category)
    }
    return a.display_name.localeCompare(b.display_name)
  })
})

// Methods
const clearFilters = () => {
  searchQuery.value = ''
  selectedCategory.value = null
}

// Watch for prop changes to reset local state if needed
watch(() => props.hunts, () => {
  // If selected category no longer exists, clear it
  if (selectedCategory.value && !categoryOptions.value.some(opt => opt.value === selectedCategory.value)) {
    selectedCategory.value = null
  }
})
</script>

<style scoped>
.hunt-catalog {
  width: 100%;
}

.hunt-list {
  display: flex;
  flex-direction: column;
}
</style>