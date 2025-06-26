import { storage, CONFIG_KEYS } from './storage.js';

class OwlculusAPI {
  constructor() {
    this.baseURL = null;
    this.token = null;
    this.tokenType = 'bearer';
  }

  async initialize() {
    const config = await storage.get([
      CONFIG_KEYS.API_ENDPOINT,
      CONFIG_KEYS.AUTH_TOKEN,
      CONFIG_KEYS.TOKEN_TYPE
    ]);
    
    this.baseURL = config[CONFIG_KEYS.API_ENDPOINT] || 'http://localhost:8000';
    this.token = config[CONFIG_KEYS.AUTH_TOKEN];
    this.tokenType = config[CONFIG_KEYS.TOKEN_TYPE] || 'bearer';
  }

  async request(endpoint, options = {}) {
    await this.initialize();
    
    const url = `${this.baseURL}${endpoint}`;
    const headers = {
      ...options.headers
    };

    if (this.token && !options.skipAuth) {
      headers['Authorization'] = `${this.tokenType} ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers
      });

      if (!response.ok) {
        let error;
        const responseText = await response.text();
        
        try {
          error = JSON.parse(responseText);
        } catch {
          error = { detail: responseText || `HTTP ${response.status}: ${response.statusText}` };
        }
        
        if (error.detail && Array.isArray(error.detail)) {
          const errorMessages = error.detail.map(e => `${e.loc?.join('.')} - ${e.msg}`).join(', ');
          throw new Error(`Validation errors: ${errorMessages}`);
        }
        
        throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      return response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async login(username, password) {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const response = await this.request('/api/auth/login', {
      method: 'POST',
      body: formData,
      skipAuth: true
    });

    if (response.access_token) {
      await storage.set({
        [CONFIG_KEYS.AUTH_TOKEN]: response.access_token,
        [CONFIG_KEYS.TOKEN_TYPE]: response.token_type || 'bearer'
      });
      
      this.token = response.access_token;
      this.tokenType = response.token_type || 'bearer';
    }

    return response;
  }

  async getCurrentUser() {
    return this.request('/api/users/me');
  }

  async getCases() {
    return this.request('/api/cases/');
  }

  async createFolder(caseId, folderName) {
    return this.request('/api/evidence/folders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: folderName,
        case_id: caseId
      })
    });
  }

  async getFolderTree(caseId) {
    return this.request(`/api/evidence/case/${caseId}/folder-tree`);
  }

  async uploadEvidence(caseId, title, htmlContent, pageUrl, category = 'Documents') {
    try {
      const folders = await this.getFolderTree(caseId);
      if (!folders || folders.length === 0) {
        await this.createFolder(caseId, 'Web Captures');
      }
    } catch (error) {
      console.warn('Could not check/create folders:', error);
    }

    const formData = new FormData();
    
    const htmlBlob = new Blob([htmlContent], { type: 'text/html' });
    const filename = `${title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_${Date.now()}.html`;
    
    // Create a File object from the Blob (Files are Blobs with additional properties)
    const file = new File([htmlBlob], filename, { type: 'text/html' });
    
    formData.append('files', file);
    
    // Only append description if it exists (matching web app behavior)
    const description = `Captured from: ${pageUrl}`;
    if (description) {
      formData.append('description', description);
    }

    const queryParams = new URLSearchParams({
      title: title,
      case_id: caseId, // URLSearchParams will convert to string automatically
      category: category
    });


    return this.request(`/api/evidence/?${queryParams}`, {
      method: 'POST',
      body: formData
    });
  }

  async uploadScreenshot(caseId, title, imageBlob, pageUrl, category = 'Other') {
    try {
      const folders = await this.getFolderTree(caseId);
      if (!folders || folders.length === 0) {
        await this.createFolder(caseId, 'Screenshots');
      }
    } catch (error) {
      console.warn('Could not check/create folders:', error);
    }

    const formData = new FormData();
    
    const filename = `${title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_${Date.now()}.png`;
    const file = new File([imageBlob], filename, { type: 'image/png' });
    
    formData.append('files', file);
    
    const description = `Screenshot captured from: ${pageUrl}`;
    if (description) {
      formData.append('description', description);
    }

    const queryParams = new URLSearchParams({
      title: title,
      case_id: caseId,
      category: category
    });

    return this.request(`/api/evidence/?${queryParams}`, {
      method: 'POST',
      body: formData
    });
  }

  async logout() {
    await storage.remove([
      CONFIG_KEYS.AUTH_TOKEN,
      CONFIG_KEYS.TOKEN_TYPE,
      CONFIG_KEYS.USER_DATA
    ]);
    
    this.token = null;
    this.tokenType = 'bearer';
  }
}

export const api = new OwlculusAPI();