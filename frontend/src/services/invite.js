import api from './api'

export const inviteService = {
  async getInvites() {
    return (await api.get('/api/invites/')).data
  },

  async createInvite(inviteData) {
    return (await api.post('/api/invites/', inviteData)).data
  },

  async deleteInvite(id) {
    return (await api.delete(`/api/invites/${id}`)).data
  },

  async validateInvite(token) {
    return (await api.post('/api/invites/validate', { token })).data
  },

  async registerUserWithInvite(registrationData) {
    return (await api.post('/api/invites/register', registrationData)).data
  },

  async cleanupExpiredInvites() {
    return (await api.post('/api/invites/cleanup')).data
  },
}
