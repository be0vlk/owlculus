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
  async sendMessage(content, caseId, id, focus = []) {
    return (
      await api.post(`${base(caseId)}/${id}/messages`, {
        content,
        ...(focus.length ? { focus } : {}),
      })
    ).data
  },
  async sources(caseId) {
    return (await api.get(`/api/strixy/cases/${caseId}/sources`)).data
  },
  async source(caseId, sourceId) {
    return (await api.get(`/api/strixy/cases/${caseId}/sources/${encodeURIComponent(sourceId)}`))
      .data
  },
}
