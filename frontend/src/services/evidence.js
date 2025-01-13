import api from './api';

export const evidenceService = {
  async getEvidenceForCase(caseId) {
    const response = await api.get(`/api/evidence/case/${caseId}`);
    return response.data;
  },

  async createEvidence({ description, category, caseId, files }) {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    
    const queryParams = new URLSearchParams({
      title: 'Multiple Files',  // This will be overridden by filenames in backend
      case_id: caseId,
      category,
    });
    if (description) {
      formData.append('description', description);
    }

    const response = await api.post(`/api/evidence?${queryParams}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async downloadEvidence(evidenceId) {
    const response = await api.get(`/api/evidence/${evidenceId}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },

  async deleteEvidence(evidenceId) {
    await api.delete(`/api/evidence/${evidenceId}`);
  },
};
