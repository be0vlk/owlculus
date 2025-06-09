import api from './api'

export const systemService = {
  async checkApiKeyStatus(provider) {
    const response = await api.get(`/api/admin/configuration/api-keys/${provider}/status`)
    return response.data
  },

  async getEvidenceFolderTemplates() {
    const response = await api.get('/api/admin/configuration/evidence-templates')
    return response.data
  },

  async updateEvidenceFolderTemplates(templates) {
    const response = await api.put('/api/admin/configuration/evidence-templates', {
      templates,
    })
    return response.data
  },
}
