import api from './api'

/**
 * Task API service for managing case tasks
 */
export const taskService = {
  /**
   * Get all available task templates
   * @param {boolean} includeInactive - Whether to include inactive templates
   * @returns {Promise<Array>} List of task templates
   */
  async getTemplates(includeInactive = false) {
    const response = await api.get('/api/tasks/templates', {
      params: { include_inactive: includeInactive },
    })
    return response.data
  },

  /**
   * Create a custom task template (Admin only)
   * @param {Object} template - Template data
   * @returns {Promise<Object>} Created template
   */
  async createCustomTemplate(template) {
    const response = await api.post('/api/tasks/templates', template)
    return response.data
  },

  /**
   * Update a task template (Admin only)
   * @param {number} templateId - Template ID
   * @param {Object} updates - Update data
   * @returns {Promise<Object>} Updated template
   */
  async updateTemplate(templateId, updates) {
    const response = await api.put(`/api/tasks/templates/${templateId}`, updates)
    return response.data
  },

  /**
   * Delete a task template (Admin only)
   * @param {number} templateId - Template ID
   * @returns {Promise<Object>} Success message
   */
  async deleteTemplate(templateId) {
    const response = await api.delete(`/api/tasks/templates/${templateId}`)
    return response.data
  },

  /**
   * Get tasks with optional filters
   * @param {Object} filters - Filter options
   * @returns {Promise<Array>} List of tasks
   */
  async getTasks(filters = {}) {
    const response = await api.get('/api/tasks/', { params: filters })
    return response.data
  },

  /**
   * Get a specific task by ID
   * @param {number} taskId - Task ID
   * @returns {Promise<Object>} Task details
   */
  async getTask(taskId) {
    const response = await api.get(`/api/tasks/${taskId}`)
    return response.data
  },

  /**
   * Create a new task
   * @param {Object} taskData - Task data
   * @returns {Promise<Object>} Created task
   */
  async createTask(taskData) {
    const response = await api.post('/api/tasks/', taskData)
    return response.data
  },

  /**
   * Update a task
   * @param {number} taskId - Task ID
   * @param {Object} updates - Update data
   * @returns {Promise<Object>} Updated task
   */
  async updateTask(taskId, updates) {
    const response = await api.put(`/api/tasks/${taskId}`, updates)
    return response.data
  },

  /**
   * Delete a task (Admin only)
   * @param {number} taskId - Task ID
   * @returns {Promise<Object>} Success message
   */
  async deleteTask(taskId) {
    const response = await api.delete(`/api/tasks/${taskId}`)
    return response.data
  },

  /**
   * Assign or unassign a task to/from a user
   * @param {number} taskId - Task ID
   * @param {number|null} userId - User ID (null to unassign)
   * @returns {Promise<Object>} Updated task
   */
  async assignTask(taskId, userId) {
    const response = await api.post(`/api/tasks/${taskId}/assign`, null, {
      params: { user_id: userId },
    })
    return response.data
  },

  /**
   * Update task status
   * @param {number} taskId - Task ID
   * @param {string} status - New status
   * @returns {Promise<Object>} Updated task
   */
  async updateStatus(taskId, status) {
    const response = await api.put(`/api/tasks/${taskId}/status`, null, {
      params: { status },
    })
    return response.data
  },

  /**
   * Bulk assign tasks to a user
   * @param {Array<number>} taskIds - Array of task IDs
   * @param {number|null} userId - User ID (null to unassign)
   * @returns {Promise<Array>} Updated tasks
   */
  async bulkAssign(taskIds, userId) {
    const response = await api.post('/api/tasks/bulk/assign', {
      task_ids: taskIds,
      user_id: userId,
    })
    return response.data
  },

  /**
   * Bulk update task status
   * @param {Array<number>} taskIds - Array of task IDs
   * @param {string} status - New status
   * @returns {Promise<Array>} Updated tasks
   */
  async bulkUpdateStatus(taskIds, status) {
    const response = await api.post('/api/tasks/bulk/status', {
      task_ids: taskIds,
      status,
    })
    return response.data
  },

  /**
   * Get tasks for a specific case
   * @param {number} caseId - Case ID
   * @returns {Promise<Array>} List of case tasks
   */
  async getCaseTasks(caseId) {
    return this.getTasks({ case_id: caseId })
  },

  /**
   * Create a task for a specific case
   * @param {number} caseId - Case ID
   * @param {Object} taskData - Task data
   * @returns {Promise<Object>} Created task
   */
  async createCaseTask(caseId, taskData) {
    return this.createTask({ ...taskData, case_id: caseId })
  },
}

export default taskService
