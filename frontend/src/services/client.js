import api from './api';

export const clientService = {
  async getClients() {
    const response = await api.get('/api/clients');
    return response.data;
  },

  async getClient(id) {
    const response = await api.get(`/api/clients/${id}`);
    return response.data;
  },

  async createClient(client) {
    const response = await api.post('/api/clients', client);
    return response.data;
  },

  async updateClient(id, client) {
    const response = await api.put(`/api/clients/${id}`, client);
    return response.data;
  },

  async deleteClient(id) {
    const response = await api.delete(`/api/clients/${id}`);
    return response.data;
  }
};
