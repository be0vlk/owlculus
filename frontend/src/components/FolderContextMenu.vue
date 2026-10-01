<template>
  <v-menu
    v-model="menu"
    :activator="activator"
    :open-on-click="false"
    location="bottom start"
    offset="2"
  >
    <v-list density="compact" min-width="180">
      <v-list-item
        v-if="canUpload"
        prepend-icon="mdi-folder-plus"
        title="Create Subfolder"
        @click="act('createSubfolder')"
      />

      <v-list-item
        v-if="canUpload"
        prepend-icon="mdi-upload"
        title="Upload Files"
        @click="act('uploadFiles')"
      />

      <v-divider v-if="canUpload" />

      <v-list-item
        v-if="canDelete"
        prepend-icon="mdi-pencil"
        title="Rename"
        @click="act('rename')"
      />

      <v-list-item
        v-if="canDelete"
        prepend-icon="mdi-delete"
        title="Delete"
        @click="act('delete')"
        class="text-error"
      />

      <v-divider v-if="canDelete && (canCopyHash || canExtractMetadata)" />

      <v-list-item
        v-if="canExtractMetadata"
        prepend-icon="mdi-file-image"
        title="Extract Metadata"
        @click="act('extractMetadata')"
      />

      <v-list-item
        v-if="canCopyHash"
        prepend-icon="mdi-content-copy"
        title="Copy Hash"
        @click="copyHash"
      />
    </v-list>
  </v-menu>
</template>

<script setup>
import { computed } from 'vue'
import { copyToClipboard } from '@/utils/clipboard'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  activator: {
    type: [String, Object],
    default: null,
  },
  item: {
    type: Object,
    default: null,
  },
  userRole: {
    type: String,
    default: 'Investigator',
  },
})

const emit = defineEmits([
  'update:modelValue',
  'createSubfolder',
  'uploadFiles',
  'rename',
  'delete',
  'extractMetadata',
])

const METADATA_EXTENSIONS = new Set(
  'jpg jpeg png gif bmp tiff tif webp heic heif raw cr2 nef arw dng mp4 avi mov wmv flv webm mkv m4v 3gp pdf doc docx xls xlsx ppt pptx'.split(
    ' ',
  ),
)

const menu = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const canDelete = computed(() => props.userRole !== 'Analyst')
const canUpload = computed(() => props.item?.is_folder && canDelete.value)
const canCopyHash = computed(() => props.item && !props.item.is_folder && props.item.file_hash)
const canExtractMetadata = computed(
  () =>
    props.item &&
    !props.item.is_folder &&
    METADATA_EXTENSIONS.has((props.item.title || '').split('.').pop().toLowerCase()),
)

const act = (name) => {
  menu.value = false
  emit(name, props.item)
}

const copyHash = () => {
  menu.value = false
  copyToClipboard(props.item.file_hash)
}
</script>
