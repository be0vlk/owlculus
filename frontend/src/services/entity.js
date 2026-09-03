import api from './api'
import { createDownloadArtifact } from '@/utils/download'

const ENTITY_FETCH_PAGE_SIZE = 1000

export const entityService = {
  async getCaseEntities(caseId) {
    const entities = []
    let skip = 0

    while (true) {
      const response = await api.get(`/api/cases/${caseId}/entities`, {
        params: { skip, limit: ENTITY_FETCH_PAGE_SIZE },
      })
      const page = response.data || []
      entities.push(...page)
      if (page.length < ENTITY_FETCH_PAGE_SIZE) return entities
      skip += ENTITY_FETCH_PAGE_SIZE
    }
  },

  async getCaseEntitiesPaginated(caseId, params = {}) {
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
      pages: Math.ceil(parseInt(total) / (params.limit || 25)),
    }
  },

  async createEntity(caseId, entityData) {
    const response = await api.post(`/api/cases/${caseId}/entities`, entityData)
    return response.data
  },

  async updateEntity(caseId, entityId, entityData) {
    const response = await api.put(`/api/cases/${caseId}/entities/${entityId}`, entityData)
    return response.data
  },

  async deleteEntity(caseId, entityId) {
    await api.delete(`/api/cases/${caseId}/entities/${entityId}`)
  },

  async getEntity(caseId, entityId) {
    const response = await api.get(`/api/cases/${caseId}/entities/${entityId}`)
    return response.data
  },

  async exportEntities(caseId, { format = 'csv', entityTypes = [], search = '' } = {}) {
    const queryParams = new URLSearchParams({ format })
    entityTypes.forEach((type) => queryParams.append('entity_type', type))
    if (search) queryParams.append('search', search)

    const response = await api.get(
      `/api/cases/${caseId}/entities/export?${queryParams.toString()}`,
      {
        responseType: 'blob',
      },
    )
    return createDownloadArtifact(response.data, response.headers)
  },
}
