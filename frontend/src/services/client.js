import api from './api'

export const clientService = {
  async getClients() {
    return (await api.get('/api/clients/')).data
  },

  async getClient(id) {
    return (await api.get(`/api/clients/${id}`)).data
  },

  async createClient(client) {
    return (await api.post('/api/clients/', client)).data
  },

  async updateClient(id, client) {
    return (await api.put(`/api/clients/${id}`, client)).data
  },

  async deleteClient(id) {
    return (await api.delete(`/api/clients/${id}`)).data
  },
}
