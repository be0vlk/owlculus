import api from './api'

export const caseService = {
  async getCases(params = {}) {
    return (await api.get('/api/cases/', { params })).data
  },

  async getCase(id) {
    return (await api.get(`/api/cases/${id}`)).data
  },

  async exportCase(id) {
    const response = await api.get(`/api/cases/${id}/export`, {
      responseType: 'blob',
    })
    return { blob: response.data, headers: response.headers }
  },

  async createCase(caseData) {
    return (await api.post('/api/cases/', caseData)).data
  },

  async updateCase(id, caseData) {
    return (await api.put(`/api/cases/${id}`, caseData)).data
  },

  async addUserToCase(caseId, userId, isLead = false) {
    return (await api.post(`/api/cases/${caseId}/users/${userId}`, { is_lead: isLead })).data
  },

  async removeUserFromCase(caseId, userId) {
    return (await api.delete(`/api/cases/${caseId}/users/${userId}`)).data
  },

  async updateCaseUserLeadStatus(caseId, userId, isLead) {
    return (await api.patch(`/api/cases/${caseId}/users/${userId}`, { is_lead: isLead })).data
  },

  async getCaseUsers(caseId) {
    return (await api.get(`/api/cases/${caseId}/users`)).data
  },
}
