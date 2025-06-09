import api from './api'

export const inviteService = {
  async getInvites() {
    const response = await api.get('/api/invites')
    return response.data
  },

  async createInvite(inviteData) {
    const response = await api.post('/api/invites', inviteData)
    return response.data
  },

  async deleteInvite(id) {
    const response = await api.delete(`/api/invites/${id}`)
    return response.data
  },

  async validateInvite(token) {
    const response = await api.get(`/api/invites/${token}/validate`)
    return response.data
  },

  async registerUserWithInvite(registrationData) {
    const response = await api.post(
      `/api/invites/${registrationData.token}/register`,
      registrationData,
    )
    return response.data
  },

  async cleanupExpiredInvites() {
    const response = await api.post('/api/invites/cleanup')
    return response.data
  },
}
