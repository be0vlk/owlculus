<template>
  <v-main>
    <v-container class="fill-height d-flex align-center justify-center" fluid>
      <div aria-live="polite" class="text-center" role="status">
        <v-progress-circular :size="48" :width="5" color="primary" indeterminate />
        <p class="text-body-medium text-medium-emphasis mt-4">Loading...</p>
      </div>
    </v-container>
  </v-main>
</template>
