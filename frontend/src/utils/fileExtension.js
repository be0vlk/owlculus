export const FileExtensionGroups = Object.freeze({
  PDF: ['pdf'],
  WORD: ['doc', 'docx'],
  IMAGE: ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'],
  VIDEO: ['mp4', 'avi', 'mov'],
  AUDIO: ['mp3', 'wav'],
  TEXT: ['txt', 'log', 'csv', 'json', 'md', 'yaml', 'yml', 'xml', 'html', 'css', 'js', 'py', 'sql', 'conf', 'ini', 'cfg'],
})

export const FileTypeIcons = Object.freeze({
  PDF: 'mdi-file-pdf-box',
  WORD: 'mdi-file-word-box',
  IMAGE: 'mdi-file-image',
  VIDEO: 'mdi-file-video',
  AUDIO: 'mdi-file-music',
  TEXT: 'mdi-file-document-outline',
  DEFAULT: 'mdi-file-document',
})

export const MimeGroups = Object.freeze({
  IMAGE: ['image/*'],
  VIDEO: ['video/*'],
  AUDIO: ['audio/*'],
  PDF: ['application/pdf'],
  WORD: ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
})

export const SUPPORTED_PREVIEW_TYPES = Object.freeze([
  'TEXT',
  'IMAGE',
]);

/**
 * Get file type group by extension
 * @param {string} ext file extension (without dot)
 * @returns {string} one of keys of FileExtensionGroups or 'DEFAULT'
 */
export function getFileTypeByExtension(ext) {
  const normalizedExt = ext.toLowerCase()

  for (const [group, extensions] of Object.entries(FileExtensionGroups)) {
    if (extensions.includes(normalizedExt)) {
      return group
    }
  }

  return 'DEFAULT'
}

/**
 * Get icon for file extension
 * @param {string} ext file extension (without dot)
 * @returns {string} icon name
 */
export function getIconByExtension(ext) {
  const type = getFileTypeByExtension(ext)
  return FileTypeIcons[type] || FileTypeIcons.DEFAULT
}

export function getFileTypeByMime(mimeType) {
  if (!mimeType) {
    return 'DEFAULT';
  }
  const normalizedMime = mimeType.toLowerCase();

  for (const [group, mimePatterns] of Object.entries(MimeGroups)) {
    for (const pattern of mimePatterns) {
      if (pattern.endsWith('/*')) {
        const prefix = pattern.slice(0, -2);
        if (normalizedMime.startsWith(prefix + '/')) {
          return group;
        }
      } else {
        if (normalizedMime === pattern) {
          return group;
        }
      }
    }
  }
  return 'DEFAULT';
}
