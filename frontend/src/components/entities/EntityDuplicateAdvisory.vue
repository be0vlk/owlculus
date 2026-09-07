<template>
  <v-alert v-if="candidates.length" type="warning" variant="tonal" class="ma-4">
    <p>
      Possible duplicates in this Case (up to 20 candidates). These matches do not prove identity.
    </p>
    <ul>
      <li v-for="candidate in candidates" :key="candidate.id">
        <a :href="`/case/${caseId}?entity=${candidate.id}`" target="_blank" rel="noopener"
          >{{ candidate.label }} (#{{ candidate.id }})</a
        >
        <span v-for="(value, field) in candidate.identifiers" :key="field">
          · {{ field }}: {{ value }}</span
        >
        <p>{{ candidate.reason }}</p>
      </li>
    </ul>
    <v-btn
      v-if="!candidates.some((item) => item.blocking)"
      :disabled="loading"
      @click="$emit('continue')"
      >Keep separate {{ entityType === 'person' ? 'Person' : 'Vehicle' }}</v-btn
    >
  </v-alert>
</template>
<script setup>
defineProps({
  candidates: { type: Array, required: true },
  caseId: { type: [String, Number], required: true },
  entityType: String,
  loading: Boolean,
})
defineEmits(['continue'])
</script>
