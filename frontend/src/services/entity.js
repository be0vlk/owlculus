import api from './api'

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

  async getDuplicateAdvisories(caseId, payload, excludeId) {
    return (
      await api.post(`/api/cases/${caseId}/entities/duplicate-advisories`, payload, {
        params: { exclude_id: excludeId },
      })
    ).data
  },

  async createEntity(caseId, entityData) {
    return (await api.post(`/api/cases/${caseId}/entities`, entityData)).data
  },

  async updateEntity(caseId, entityId, entityData) {
    return (await api.put(`/api/cases/${caseId}/entities/${entityId}`, entityData)).data
  },

  async deleteEntity(caseId, entityId) {
    await api.delete(`/api/cases/${caseId}/entities/${entityId}`)
  },

  async getEntity(caseId, entityId) {
    return (await api.get(`/api/cases/${caseId}/entities/${entityId}`)).data
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
    return { blob: response.data, headers: response.headers }
  },
}
