import { createExecutionStream, closeExecutionStream } from './executionStream'
import api from './api'
import { submitExecution } from './executionSubmission'
import { createDownloadArtifact } from '@/utils/download'

/**
 * Hunt API service for managing OSINT hunt workflows
 */
export const huntService = {
  /**
   * Get all available hunts
   * @returns {Promise<Array>} List of hunt definitions
   */
  async getHunts(signal) {
    const response = await api.get('/api/hunts/', { signal })
    return response.data
  },

  /**
   * Get a specific hunt by ID
   * @param {number} huntId - Hunt ID
   * @returns {Promise<Object>} Hunt definition
   */
  async getHunt(huntId, signal) {
    const response = await api.get(`/api/hunts/${huntId}`, { signal })
    return response.data
  },

  /**
   * Execute a hunt workflow
   * @param {number} huntId - Hunt ID to execute
   * @param {number} caseId - Case ID to run hunt for
   * @param {Object} parameters - Hunt parameters
   * @returns {Promise<Object>} Hunt execution details
   */
  async executeHunt(huntId, caseId, parameters) {
    return submitExecution(`/api/hunts/${huntId}/execute`, {
      case_id: caseId,
      parameters: parameters || {},
    })
  },

  /**
   * Get hunt execution status and details
   * @param {number} executionId - Hunt execution ID
   * @param {boolean} includeSteps - Whether to include step details
   * @returns {Promise<Object>} Hunt execution details
   */
  async getExecution(executionId, includeSteps = false, signal) {
    const response = await api.get(`/api/hunts/executions/${executionId}`, {
      params: { include_steps: includeSteps },
      signal,
    })
    return response.data
  },

  async exportExecution(executionId, format) {
    const response = await api.get(`/api/hunts/executions/${executionId}/export`, {
      params: { format },
      responseType: 'blob',
    })
    return createDownloadArtifact(response.data, response.headers)
  },

  /**
   * Get all hunt executions for a case
   * @param {number} caseId - Case ID
   * @returns {Promise<Array>} List of hunt executions
   */
  async getCaseExecutions(caseId, signal) {
    const response = await api.get(`/api/hunts/cases/${caseId}/executions`, { signal })
    return response.data
  },

  /**
   * Cancel a running hunt execution
   * @param {number} executionId - Hunt execution ID
   * @returns {Promise<Object>} Cancellation result
   */
  async cancelExecution(executionId) {
    const response = await api.delete(`/api/hunts/executions/${executionId}`)
    return response.data
  },

  /**
   * Create WebSocket connection for real-time hunt execution updates
   * @param {number} executionId - Hunt execution ID
   * @param {Function} onMessage - Message handler function
   * @param {Function} onError - Error handler function
   * @returns {WebSocket} WebSocket connection
   */
  createExecutionStream(executionId, onMessage, onError, cursor) {
    return createExecutionStream('hunt', executionId, onMessage, onError, cursor)
  },

  closeExecutionStream,
}

export default huntService
