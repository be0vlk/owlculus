import api from './api'

export const caseService = {
  async getCases (params = {}) {
    const response = await api.get('/api/cases', { params })
    return response.data
  },

  async getCase (id) {
    const response = await api.get(`/api/cases/${id}`)
    return response.data
  },

  async createCase (caseData) {
    const response = await api.post('/api/cases', caseData)
    return response.data
  },

  async updateCase (id, caseData) {
    const response = await api.put(`/api/cases/${id}`, caseData)
    return response.data
  },

  async addUserToCase (caseId, userId) {
    const response = await api.post(`/api/cases/${caseId}/users/${userId}`)
    return response.data
  },

  async removeUserFromCase (caseId, userId) {
    const response = await api.delete(`/api/cases/${caseId}/users/${userId}`)
    return response.data
  }
}
