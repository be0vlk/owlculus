export const ENTITY_TYPES = [
  { value: 'person', title: 'Person', icon: 'mdi-account', color: 'indigo' },
  { value: 'company', title: 'Company', icon: 'mdi-domain', color: 'teal-darken-2' },
  { value: 'domain', title: 'Domain', icon: 'mdi-web', color: 'deep-purple' },
  { value: 'ip_address', title: 'IP Address', icon: 'mdi-ip', color: 'amber-darken-2' },
  { value: 'vehicle', title: 'Vehicle', icon: 'mdi-car', color: 'brown' },
]

export const entityType = (type) => ENTITY_TYPES.find((t) => t.value === type)

const SECTION_ICONS = {
  basicInfo: 'mdi-information',
  address: 'mdi-map-marker',
  socialMedia: 'mdi-cellphone',
  associates: 'mdi-account-group',
  executives: 'mdi-account-tie',
  affiliates: 'mdi-handshake',
  contact: 'mdi-phone',
  technical: 'mdi-server',
  notes: 'mdi-note-text',
  registration: 'mdi-card-text',
}
export const sectionIcon = (sectionKey) => SECTION_ICONS[sectionKey] || 'mdi-folder'

const FIELD_ICONS = {
  email: 'mdi-email',
  tel: 'mdi-phone',
  url: 'mdi-link',
  textarea: 'mdi-text',
  number: 'mdi-numeric',
  date: 'mdi-calendar',
}
export const fieldIcon = (fieldType) => FIELD_ICONS[fieldType] || 'mdi-form-textbox'

const SOCIAL_MEDIA_ICONS = {
  bluesky: 'mdi-cloud',
  discord: 'mdi-message-text',
  facebook: 'mdi-facebook',
  instagram: 'mdi-instagram',
  linkedin: 'mdi-linkedin',
  reddit: 'mdi-reddit',
  telegram: 'mdi-send',
  tiktok: 'mdi-music-note',
  twitch: 'mdi-twitch',
  x: 'mdi-twitter',
  youtube: 'mdi-youtube',
  other: 'mdi-link-variant',
}
export const socialMediaIcon = (platform) => SOCIAL_MEDIA_ICONS[platform] || 'mdi-link'
