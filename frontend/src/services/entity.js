import api from './api';

export const entityService = {
  async getCaseEntities(caseId) {
    const response = await api.get(`/api/cases/${caseId}/entities`);
    return response.data;
  },

  async createEntity(caseId, entityData) {
    const response = await api.post(`/api/cases/${caseId}/entities`, entityData);
    return response.data;
  },

  async updateEntity(caseId, entityId, entityData) {
    const response = await api.put(`/api/cases/${caseId}/entities/${entityId}`, entityData);
    return response.data;
  },

  async deleteEntity(entityId) {
    await api.delete(`/api/entities/${entityId}`);
  }
};
