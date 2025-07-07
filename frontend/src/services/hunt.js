import api from './api'

/**
 * Hunt API service for managing OSINT hunt workflows
 */
export const huntService = {
  /**
   * Get all available hunts
   * @returns {Promise<Array>} List of hunt definitions
   */
  async getHunts() {
    const response = await api.get('/api/hunts/')
    return response.data
  },

  /**
   * Get a specific hunt by ID
   * @param {number} huntId - Hunt ID
   * @returns {Promise<Object>} Hunt definition
   */
  async getHunt(huntId) {
    const response = await api.get(`/api/hunts/${huntId}`)
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
    const response = await api.post(`/api/hunts/${huntId}/execute`, {
      case_id: caseId,
      parameters: parameters || {},
    })
    return response.data
  },

  /**
   * Get hunt execution status and details
   * @param {number} executionId - Hunt execution ID
   * @param {boolean} includeSteps - Whether to include step details
   * @returns {Promise<Object>} Hunt execution details
   */
  async getExecution(executionId, includeSteps = false) {
    const response = await api.get(`/api/hunts/executions/${executionId}`, {
      params: { include_steps: includeSteps },
    })
    return response.data
  },

  /**
   * Get all hunt executions for a case
   * @param {number} caseId - Case ID
   * @returns {Promise<Array>} List of hunt executions
   */
  async getCaseExecutions(caseId) {
    const response = await api.get(`/api/hunts/cases/${caseId}/executions`)
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
  async createExecutionStream(executionId, onMessage, onError) {
    try {
      // Request ephemeral token from the API
      const response = await api.post('/api/auth/websocket-token', {
        execution_id: executionId
      })
      
      const { token } = response.data
      
      const wsUrl = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000'
      const ws = new WebSocket(`${wsUrl}/api/hunts/executions/${executionId}/stream?token=${encodeURIComponent(token)}`)

      ws.onopen = () => {
        console.log(`Hunt execution ${executionId} stream connected`)
      }

    ws.onmessage = (event) => {
      try {
        // Skip non-JSON messages like "pong" heartbeats
        if (event.data === 'pong' || event.data === 'ping') {
          return
        }

        const data = JSON.parse(event.data)
        onMessage(data)
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
        onError?.(error)
      }
    }

    ws.onerror = (error) => {
      console.error('Hunt execution stream error:', error)
      onError?.(error)
    }

    ws.onclose = (event) => {
      console.log(`Hunt execution ${executionId} stream closed:`, event.code, event.reason)
    }

    // Add ping functionality to keep connection alive
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      } else {
        clearInterval(pingInterval)
      }
    }, 30000) // Ping every 30 seconds

    // Store ping interval on WebSocket for cleanup
    ws._pingInterval = pingInterval

      return ws
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      onError?.(error)
      throw error
    }
  },

  /**
   * Close WebSocket connection and cleanup
   * @param {WebSocket} ws - WebSocket connection to close
   */
  closeExecutionStream(ws) {
    if (ws) {
      if (ws._pingInterval) {
        clearInterval(ws._pingInterval)
      }
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  },
}

export default huntService
