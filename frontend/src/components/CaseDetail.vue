<template>
    <div class="col-span-2">
        <div class="grid grid-cols-2 gap-4">
            <div>
                <BaseDisplayField label="Title" :value="caseData?.title" />
            </div>
            <div>
                <BaseDisplayField label="Status" :value="caseData?.status" />
            </div>
            <div>
                <BaseDisplayField label="Client" :value="client?.name || 'No client assigned'" />
            </div>
            <div>
                <BaseDisplayField label="Created Date" :value="formatDate(caseData?.created_at)" />
            </div>
            <div>
                <BaseDisplayField label="Assigned Users" :value="caseData?.users?.map(user => user.username).join(', ') || 'No users assigned'" />
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue';
import BaseDisplayField from './BaseDisplayField.vue';
import { formatDate } from '../composables/dateUtils';

const props = defineProps({
  caseData: { type: Object, required: true },
  client: { type: Object, default: () => ({}) },
});
</script>