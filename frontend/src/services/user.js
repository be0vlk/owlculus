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
    return (await api.post('/api/users/', userData)).data
  },

  async updateUser(id, userData) {
    return (await api.put(`/api/users/${id}`, userData)).data
  },

  async deleteUser(id) {
    return (await api.delete(`/api/users/${id}`)).data
  },

  async resetPassword(id, newPassword) {
    return (await api.put(`/api/users/${id}/password`, { new_password: newPassword })).data
  },
}
