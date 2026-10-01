import api from './api'

export const taskService = {
  async getTemplates(includeInactive = false) {
    const response = await api.get('/api/tasks/templates', {
      params: { include_inactive: includeInactive },
    })
    return response.data
  },

  async createCustomTemplate(template) {
    const response = await api.post('/api/tasks/templates', template)
    return response.data
  },

  async updateTemplate(templateId, updates) {
    const response = await api.put(`/api/tasks/templates/${templateId}`, updates)
    return response.data
  },

  async deleteTemplate(templateId) {
    const response = await api.delete(`/api/tasks/templates/${templateId}`)
    return response.data
  },

  async getTasks(filters = {}) {
    const response = await api.get('/api/tasks/', { params: filters })
    return response.data
  },

  async getTask(taskId) {
    const response = await api.get(`/api/tasks/${taskId}`)
    return response.data
  },

  async createTask(taskData) {
    const response = await api.post('/api/tasks/', taskData)
    return response.data
  },

  async updateTask(taskId, updates) {
    const response = await api.put(`/api/tasks/${taskId}`, updates)
    return response.data
  },

  async deleteTask(taskId) {
    const response = await api.delete(`/api/tasks/${taskId}`)
    return response.data
  },

  async assignTask(taskId, userId) {
    const response = await api.post(`/api/tasks/${taskId}/assign`, null, {
      params: { user_id: userId },
    })
    return response.data
  },

  async updateStatus(taskId, status) {
    const response = await api.put(`/api/tasks/${taskId}/status`, null, {
      params: { status },
    })
    return response.data
  },

  async bulkAssign(taskIds, userId) {
    const response = await api.post('/api/tasks/bulk/assign', {
      task_ids: taskIds,
      user_id: userId,
    })
    return response.data
  },

  async bulkUpdateStatus(taskIds, status) {
    const response = await api.post('/api/tasks/bulk/status', {
      task_ids: taskIds,
      status,
    })
    return response.data
  },
}

export default taskService
