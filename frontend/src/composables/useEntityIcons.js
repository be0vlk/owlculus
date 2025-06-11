import { computed } from 'vue'

export function useEntityIcons(entity) {
  const getEntityIcon = computed(() => {
    const iconMap = {
      person: 'mdi-account',
      company: 'mdi-domain',
      domain: 'mdi-web',
      ip_address: 'mdi-ip',
      network: 'mdi-server-network',
    }
    return iconMap[entity.value?.entity_type] || 'mdi-help-circle'
  })

  const getSectionIcon = (sectionKey) => {
    const iconMap = {
      basicInfo: 'mdi-information',
      address: 'mdi-map-marker',
      socialMedia: 'mdi-cellphone',
      associates: 'mdi-account-group',
      executives: 'mdi-account-tie',
      affiliates: 'mdi-handshake',
      contact: 'mdi-phone',
      technical: 'mdi-server',
      notes: 'mdi-note-text',
    }
    return iconMap[sectionKey] || 'mdi-folder'
  }

  const getFieldIcon = (fieldType) => {
    const iconMap = {
      email: 'mdi-email',
      tel: 'mdi-phone',
      url: 'mdi-link',
      textarea: 'mdi-text',
      text: 'mdi-form-textbox',
      number: 'mdi-numeric',
      date: 'mdi-calendar',
    }
    return iconMap[fieldType] || 'mdi-form-textbox'
  }

  return {
    getEntityIcon,
    getSectionIcon,
    getFieldIcon,
  }
}
