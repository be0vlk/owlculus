import api from './api'

const base = (caseId) => `/api/strixy/cases/${caseId}/conversations`
export const strixyService = {
  async getAvailability(caseId) {
    return (await api.get('/api/strixy/availability', { params: { case_id: caseId } })).data
  },
  async list(caseId) {
    return (await api.get(base(caseId))).data
  },
  async create(caseId) {
    return (await api.post(base(caseId))).data
  },
  async read(caseId, id) {
    return (await api.get(`${base(caseId)}/${id}`)).data
  },
  async remove(caseId, id) {
    await api.delete(`${base(caseId)}/${id}`)
  },
  async sendMessage(content, caseId, id) {
    return (
      await api.post(`${base(caseId)}/${id}/messages`, {
        content,
      })
    ).data
  },
  async control(caseId, id, runId, action) {
    return (await api.post(`${base(caseId)}/${id}/runs/${runId}/${action}`)).data
  },
  async shares(caseId, id) {
    return (await api.get(`${base(caseId)}/${id}/shares`)).data
  },
  async share(caseId, id, throughMessageId) {
    return (
      await api.post(`${base(caseId)}/${id}/shares`, { through_message_id: throughMessageId })
    ).data
  },
  async readShare(caseId, id) {
    return (await api.get(`/api/strixy/cases/${caseId}/shares/${id}`)).data
  },
  async revokeShare(caseId, id) {
    await api.delete(`/api/strixy/cases/${caseId}/shares/${id}`)
  },
  async copyShare(caseId, id) {
    return (await api.post(`/api/strixy/cases/${caseId}/shares/${id}/copy`)).data
  },
  async source(caseId, sourceId, unit) {
    return (
      await api.get(`/api/strixy/cases/${caseId}/sources/${encodeURIComponent(sourceId)}`, {
        params: unit ? { unit } : {},
      })
    ).data
  },
}
