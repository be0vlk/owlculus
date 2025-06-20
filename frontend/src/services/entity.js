import api from './api'

export const entityService = {
  async getCaseEntities (caseId) {
    const response = await api.get(`/api/cases/${caseId}/entities`)
    return response.data
  },

  async getCaseEntitiesPaginated (caseId, params = {}) {
    const queryParams = new URLSearchParams()

    // Add pagination params
    if (params.skip !== undefined) queryParams.append('skip', params.skip)
    if (params.limit !== undefined) queryParams.append('limit', params.limit)

    // Add search param
    if (params.search) queryParams.append('search', params.search)

    // Add entity type filters
    if (params.entity_types && params.entity_types.length > 0) {
      params.entity_types.forEach((type) => queryParams.append('entity_type', type))
    }

    // Add sorting params
    if (params.sort_by) queryParams.append('sort_by', params.sort_by)
    if (params.sort_desc !== undefined) queryParams.append('sort_desc', params.sort_desc)

    const response = await api.get(`/api/cases/${caseId}/entities?${queryParams.toString()}`)

    // Transform response to expected format
    // Backend returns array, we need to wrap it with pagination info
    const items = response.data
    const total = response.headers['x-total-count'] || items.length

    return {
      items,
      total: parseInt(total),
      page: Math.floor((params.skip || 0) / (params.limit || 25)) + 1,
      pages: Math.ceil(parseInt(total) / (params.limit || 25))
    }
  },

  async createEntity (caseId, entityData) {
    const response = await api.post(`/api/cases/${caseId}/entities`, entityData)
    return response.data
  },

  async updateEntity (caseId, entityId, entityData) {
    const response = await api.put(`/api/cases/${caseId}/entities/${entityId}`, entityData)
    return response.data
  },

  async deleteEntity (entityId) {
    await api.delete(`/api/entities/${entityId}`)
  }
}
