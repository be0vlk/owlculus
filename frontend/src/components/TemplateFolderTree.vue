<template>
  <div class="folder-tree">
    <template v-for="(folder, index) in folders" :key="index">
      <div class="folder-item">
        <v-icon icon="mdi-folder" size="small" class="mr-2" color="blue-darken-1" />
        <span>{{ folder.name }}</span>
        <span v-if="folder.description" class="text-caption text-medium-emphasis ml-2">
          ({{ folder.description }})
        </span>
      </div>
      <div v-if="folder.subfolders && folder.subfolders.length > 0" class="subfolder-container">
        <template-folder-tree :folders="folder.subfolders" />
      </div>
    </template>
  </div>
</template>

<script setup>
defineProps({
  folders: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.folder-tree {
  line-height: 1.5;
}

.folder-item {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.subfolder-container {
  margin-left: 20px;
  border-left: 1px solid rgba(var(--v-theme-outline), 0.2);
  padding-left: 12px;
  margin-bottom: 8px;
}
</style>