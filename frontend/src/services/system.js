import api from './api'

export const systemService = {
  async checkApiKeyStatus(provider) {
    const response = await api.get(`/api/admin/configuration/api-keys/${provider}/status`)
    return response.data
  },
}
