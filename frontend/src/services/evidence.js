import api from './api'

export const evidenceService = {
  async getEvidenceForCase(caseId) {
    const response = await api.get(`/api/evidence/case/${caseId}`)
    return response.data
  },

  async createEvidence({ description, category, caseId, files, folderPath, parentFolderId }) {
    const formData = new FormData()
    files.forEach((file) => {
      formData.append('files', file)
    })

    const queryParams = new URLSearchParams({
      title: 'Multiple Files', // This will be overridden by filenames in backend
      case_id: caseId,
      category,
    })
    if (description) {
      formData.append('description', description)
    }
    if (folderPath) {
      formData.append('folder_path', folderPath)
    }
    if (parentFolderId) {
      formData.append('parent_folder_id', parentFolderId)
    }

    const response = await api.post(`/api/evidence?${queryParams}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  async downloadEvidence(evidenceId) {
    const response = await api.get(`/api/evidence/${evidenceId}/download`, {
      responseType: 'blob',
    })
    return response.data
  },

  async deleteEvidence(evidenceId) {
    await api.delete(`/api/evidence/${evidenceId}`)
  },

  async getFolderTree(caseId) {
    const response = await api.get(`/api/evidence/case/${caseId}/folder-tree`)
    return response.data
  },

  async createFolder({ caseId, title, description, parentFolderId }) {
    const response = await api.post('/api/evidence/folders', {
      case_id: caseId,
      title,
      description,
      parent_folder_id: parentFolderId,
    })
    return response.data
  },

  async updateFolder(folderId, { title, description, parentFolderId }) {
    const response = await api.put(`/api/evidence/folders/${folderId}`, {
      title,
      description,
      parent_folder_id: parentFolderId,
    })
    return response.data
  },

  async deleteFolder(folderId) {
    await api.delete(`/api/evidence/folders/${folderId}`)
  },

  async updateEvidence(evidenceId, { title, description, category, folderPath, parentFolderId }) {
    const response = await api.put(`/api/evidence/${evidenceId}`, {
      title,
      description,
      category,
      folder_path: folderPath,
      parent_folder_id: parentFolderId,
    })
    return response.data
  },

  async extractMetadata(evidenceId) {
    const response = await api.get(`/api/evidence/${evidenceId}/metadata`)
    return response.data
  },

  async applyFolderTemplate(caseId, templateName) {
    const response = await api.post(`/api/evidence/case/${caseId}/apply-template`, null, {
      params: { template_name: templateName },
    })
    return response.data
  },
}
