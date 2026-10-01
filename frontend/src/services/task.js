import api from './api'

export const taskService = {
  async getTemplates(includeInactive = false) {
    return (
      await api.get('/api/tasks/templates', {
        params: { include_inactive: includeInactive },
      })
    ).data
  },

  async createCustomTemplate(template) {
    return (await api.post('/api/tasks/templates', template)).data
  },

  async updateTemplate(templateId, updates) {
    return (await api.put(`/api/tasks/templates/${templateId}`, updates)).data
  },

  async deleteTemplate(templateId) {
    return (await api.delete(`/api/tasks/templates/${templateId}`)).data
  },

  async getTasks(filters = {}) {
    return (await api.get('/api/tasks/', { params: filters })).data
  },

  async getTask(taskId) {
    return (await api.get(`/api/tasks/${taskId}`)).data
  },

  async createTask(taskData) {
    return (await api.post('/api/tasks/', taskData)).data
  },

  async updateTask(taskId, updates) {
    return (await api.put(`/api/tasks/${taskId}`, updates)).data
  },

  async deleteTask(taskId) {
    return (await api.delete(`/api/tasks/${taskId}`)).data
  },

  async assignTask(taskId, userId) {
    return (
      await api.post(`/api/tasks/${taskId}/assign`, null, {
        params: { user_id: userId },
      })
    ).data
  },

  async updateStatus(taskId, status) {
    return (
      await api.put(`/api/tasks/${taskId}/status`, null, {
        params: { status },
      })
    ).data
  },

  async bulkAssign(taskIds, userId) {
    return (
      await api.post('/api/tasks/bulk/assign', {
        task_ids: taskIds,
        user_id: userId,
      })
    ).data
  },

  async bulkUpdateStatus(taskIds, status) {
    return (
      await api.post('/api/tasks/bulk/status', {
        task_ids: taskIds,
        status,
      })
    ).data
  },
}

export default taskService
