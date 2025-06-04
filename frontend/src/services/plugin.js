import api from './api';

export const pluginService = {
  async listPlugins() {
    const response = await api.get('/api/plugins');
    return response.data;
  },

  async executePlugin(name, params = {}) {
    const response = await api.post(`/api/plugins/${name}/execute`, params, {
      responseType: 'text',
      transformResponse: [(data) => data], // Prevent automatic JSON parsing
    });
    
    // Try parsing as a single JSON object first
    try {
      const singleResult = JSON.parse(response.data);
      return [singleResult]; // Return as array for consistency
    } catch {
      // If single parse fails, try splitting into multiple JSON objects
      const results = response.data
        .split('\n')
        .filter(line => line.trim())
        .map(line => {
          try {
            return JSON.parse(line);
          } catch {
            console.error('Failed to parse plugin response line');
            return null;
          }
        })
        .filter(Boolean); // Remove any null results from failed parsing
        
      return results;
    }
  }
};

export default pluginService;
