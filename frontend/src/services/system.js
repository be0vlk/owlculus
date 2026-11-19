import api from './api'

export const systemService = {
  async getEvidenceFolderTemplates() {
    return (await api.get('/api/admin/configuration/evidence-templates')).data
  },

  async updateEvidenceFolderTemplates(templates) {
    return (
      await api.put('/api/admin/configuration/evidence-templates', {
        templates,
      })
    ).data
  },
}
