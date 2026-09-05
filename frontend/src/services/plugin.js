import api from './api'
import { submitExecution } from './executionSubmission'

export const pluginService = {
  async listPlugins() {
    return (await api.get('/api/plugins/')).data
  },

  async executePlugin(name, params = {}, caseId) {
    if (!Number.isInteger(caseId) || caseId <= 0) {
      throw new Error('An active case is required to execute a plugin')
    }
    return submitExecution(`/api/plugins/${name}/execute`, { ...params, case_id: caseId })
  },

  async cancelExecution(id) {
    return (await api.delete(`/api/plugins/executions/${id}`)).data
  },

  async getExecution(id, signal) {
    return (await api.get(`/api/plugins/executions/${id}`, { signal })).data
  },

  async getResults(id, cursor = 0, signal) {
    return (
      await api.get(`/api/plugins/executions/${id}/results`, {
        params: { cursor, limit: 200 },
        signal,
      })
    ).data
  },

  async getHistory(caseId, cursor = 0, signal) {
    return (await api.get(`/api/plugins/executions/case/${caseId}`, { params: { cursor }, signal }))
      .data
  },
}

export default pluginService
