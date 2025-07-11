import api from './api'

export const caseService = {
  async getCases(params = {}) {
    const response = await api.get('/api/cases', { params })
    return response.data
  },

  async getCase(id) {
    const response = await api.get(`/api/cases/${id}`)
    return response.data
  },

  async createCase(caseData) {
    const response = await api.post('/api/cases', caseData)
    return response.data
  },

  async updateCase(id, caseData) {
    const response = await api.put(`/api/cases/${id}`, caseData)
    return response.data
  },

  async addUserToCase(caseId, userId, isLead = false) {
    const response = await api.post(`/api/cases/${caseId}/users/${userId}`, { is_lead: isLead })
    return response.data
  },

  async removeUserFromCase(caseId, userId) {
    const response = await api.delete(`/api/cases/${caseId}/users/${userId}`)
    return response.data
  },

  async updateCaseUserLeadStatus(caseId, userId, isLead) {
    const response = await api.patch(`/api/cases/${caseId}/users/${userId}`, { is_lead: isLead })
    return response.data
  },

  async getCaseUsers(caseId) {
    const response = await api.get(`/api/cases/${caseId}/users`)
    return response.data
  },
}
