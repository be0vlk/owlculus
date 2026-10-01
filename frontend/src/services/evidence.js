import api from './api'

export const evidenceService = {
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

    return (
      await api.post(`/api/evidence/?${queryParams}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    ).data
  },

  async downloadEvidence(evidenceId) {
    const response = await api.get(`/api/evidence/${evidenceId}/download`, {
      responseType: 'blob',
    })
    return { blob: response.data, headers: response.headers }
  },

  async deleteEvidence(evidenceId) {
    await api.delete(`/api/evidence/${evidenceId}`)
  },

  async getFolderTree(caseId) {
    return (await api.get(`/api/evidence/case/${caseId}/folder-tree`)).data
  },

  async createFolder({ caseId, title, description, parentFolderId }) {
    return (
      await api.post('/api/evidence/folders', {
        case_id: caseId,
        title,
        description,
        parent_folder_id: parentFolderId,
      })
    ).data
  },

  async updateFolder(folderId, { title }) {
    return (await api.put(`/api/evidence/folders/${folderId}`, { title })).data
  },

  async deleteFolder(folderId) {
    await api.delete(`/api/evidence/folders/${folderId}`)
  },

  async updateEvidence(evidenceId, { title, parentFolderId }) {
    return (
      await api.put(`/api/evidence/${evidenceId}`, {
        title,
        parent_folder_id: parentFolderId,
      })
    ).data
  },

  async extractMetadata(evidenceId) {
    return (await api.get(`/api/evidence/${evidenceId}/metadata`)).data
  },

  async getEvidenceContent(evidenceId) {
    return (await api.get(`/api/evidence/${evidenceId}/content`)).data
  },

  async applyFolderTemplate(caseId, templateName) {
    return (
      await api.post(`/api/evidence/case/${caseId}/apply-template`, null, {
        params: { template_name: templateName },
      })
    ).data
  },
}
