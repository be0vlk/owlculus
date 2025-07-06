import api from './api'

export const userService = {
  async getUsers() {
    const response = await api.get('/api/users')
    return response.data
  },

  async createUser(userData) {
    const response = await api.post('/api/users', userData)
    return response.data
  },

  async updateUser(id, userData) {
    const response = await api.put(`/api/users/${id}`, userData)
    return response.data
  },

  async deleteUser(id) {
    const response = await api.delete(`/api/users/${id}`)
    return response.data
  },

  async updateUserRole(id, role) {
    const response = await api.put(`/api/users/${id}/role`, { role })
    return response.data
  },

  async resetPassword(id, newPassword) {
    const response = await api.put(`/api/users/${id}/password`, { new_password: newPassword })
    return response.data
  },
}
