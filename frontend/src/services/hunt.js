import { createExecutionStream, closeExecutionStream } from './executionStream'
import api from './api'
import { submitExecution } from './executionSubmission'

export const huntService = {
  async getHunts(signal) {
    return (await api.get('/api/hunts/', { signal })).data
  },

  async executeHunt(huntId, caseId, parameters) {
    return submitExecution(`/api/hunts/${huntId}/execute`, {
      case_id: caseId,
      parameters: parameters || {},
    })
  },

  async getExecution(executionId, includeSteps = false, signal) {
    return (
      await api.get(`/api/hunts/executions/${executionId}`, {
        params: { include_steps: includeSteps },
        signal,
      })
    ).data
  },

  async exportExecution(executionId, format) {
    const response = await api.get(`/api/hunts/executions/${executionId}/export`, {
      params: { format },
      responseType: 'blob',
    })
    return { blob: response.data, headers: response.headers }
  },

  async getCaseExecutions(caseId, signal) {
    return (await api.get(`/api/hunts/cases/${caseId}/executions`, { signal })).data
  },

  async cancelExecution(executionId) {
    return (await api.delete(`/api/hunts/executions/${executionId}`)).data
  },

  createExecutionStream(executionId, onMessage, onError, cursor) {
    return createExecutionStream('hunt', executionId, onMessage, onError, cursor)
  },

  closeExecutionStream,
}

export default huntService
