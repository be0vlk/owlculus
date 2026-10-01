import api from './api'

export const userService = {
  async getUsers() {
    const users = []
    const limit = 100
    for (let skip = 0; ; skip += limit) {
      const response = await api.get('/api/users/', { params: { skip, limit } })
      users.push(...response.data)
      if (response.data.length < limit) return users
    }
  },

  async createUser(userData) {
    const response = await api.post('/api/users/', userData)
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

  async resetPassword(id, newPassword) {
    const response = await api.put(`/api/users/${id}/password`, { new_password: newPassword })
    return response.data
  },
}
