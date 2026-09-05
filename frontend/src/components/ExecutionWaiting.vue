<template>
  <v-alert v-if="execution?.status === 'cancelling'" type="info" role="status" class="mb-4">
    Cancellation requested. Waiting for execution cleanup. Committed output is retained. If
    execution control is unavailable, confirmation can be delayed until connectivity returns; local
    work stops by its ownership lease deadline.
  </v-alert>
  <v-alert v-if="execution?.waiting_reason" type="info" role="status" class="mb-4">
    <strong v-if="execution.dispatch_state === 'recovery_waiting'">Recovery waiting. </strong>
    {{ execution.waiting_reason }}. Accepted {{ new Date(execution.created_at).toLocaleString() }}.
    <span v-if="execution.last_dispatch_at">
      Last dispatch attempt {{ new Date(execution.last_dispatch_at).toLocaleString() }}.
    </span>
    <span v-if="execution.next_dispatch_at">
      Next retry {{ new Date(execution.next_dispatch_at).toLocaleString() }}.
    </span>
  </v-alert>
</template>

<script setup>
defineProps({ execution: { type: Object, default: null } })
</script>
