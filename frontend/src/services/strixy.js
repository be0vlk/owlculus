import api from './api'

export const strixyService = {
  async sendMessage(messages) {
    const response = await api.post('/api/strixy/chat', {
      messages,
    })
    return response.data
  },
}
