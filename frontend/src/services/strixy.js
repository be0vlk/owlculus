import api from './api'

export const strixyService = {
  async sendMessage(messages, caseId) {
    if (!Number.isInteger(caseId) || caseId <= 0) throw new Error('An active case is required')
    const response = await api.post('/api/strixy/chat', {
      case_id: caseId,
      messages,
    })
    return response.data
  },
}
