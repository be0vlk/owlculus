<template>
  <v-menu
    v-model="menu"
    :activator="activator"
    location="bottom start"
    offset="2"
  >
    <v-list density="compact" min-width="180">
      <v-list-item
        v-if="canCreateSubfolder"
        prepend-icon="mdi-folder-plus"
        title="Create Subfolder"
        @click="createSubfolder"
      />
      
      <v-list-item
        v-if="canUpload"
        prepend-icon="mdi-upload"
        title="Upload Files"
        @click="uploadFiles"
      />
      
      <v-divider v-if="canCreateSubfolder || canUpload" />
      
      <v-list-item
        v-if="canRename"
        prepend-icon="mdi-pencil"
        title="Rename"
        @click="rename"
      />
      
      <v-list-item
        v-if="canDelete"
        prepend-icon="mdi-delete"
        title="Delete"
        @click="deleteItem"
        class="text-error"
      />
      
      <v-divider v-if="(canRename || canDelete) && (showProperties || canCopyHash)" />
      
      <v-list-item
        v-if="canCopyHash"
        prepend-icon="mdi-content-copy"
        title="Copy Hash"
        @click="copyHash"
      />
      
      <v-list-item
        v-if="showProperties"
        prepend-icon="mdi-information"
        title="Properties"
        @click="showItemProperties"
      />
    </v-list>
  </v-menu>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  activator: {
    type: [String, Object],
    default: null
  },
  item: {
    type: Object,
    default: null
  },
  userRole: {
    type: String,
    default: 'Investigator'
  }
})

const emit = defineEmits([
  'update:modelValue',
  'createSubfolder',
  'uploadFiles',
  'rename',
  'delete',
  'showProperties'
])

// Reactive data
const menu = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// Computed permissions
const canCreateSubfolder = computed(() => {
  return props.item?.is_folder && props.userRole !== 'Analyst'
})

const canUpload = computed(() => {
  return props.item?.is_folder && props.userRole !== 'Analyst'
})

const canRename = computed(() => {
  return props.userRole !== 'Analyst'
})

const canDelete = computed(() => {
  return props.userRole !== 'Analyst'
})

const showProperties = computed(() => {
  return !!props.item
})

const canCopyHash = computed(() => {
  return props.item && !props.item.is_folder && props.item.file_hash
})

// Methods
const createSubfolder = () => {
  menu.value = false
  emit('createSubfolder', props.item)
}

const uploadFiles = () => {
  menu.value = false
  emit('uploadFiles', props.item)
}

const rename = () => {
  menu.value = false
  emit('rename', props.item)
}

const deleteItem = () => {
  menu.value = false
  emit('delete', props.item)
}

const copyHash = async () => {
  menu.value = false
  if (props.item?.file_hash) {
    try {
      await navigator.clipboard.writeText(props.item.file_hash)
      // You could emit a success event here if you want to show a toast notification
    } catch (error) {
      console.error('Failed to copy hash to clipboard:', error)
      // Fallback: create a temporary text area and copy
      const textArea = document.createElement('textarea')
      textArea.value = props.item.file_hash
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
    }
  }
}

const showItemProperties = () => {
  menu.value = false
  emit('showProperties', props.item)
}
</script>