import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const authService = {
  async login(username, password) {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await axios.post(`${baseURL}/api/auth/login`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('token_type', response.data.token_type || 'bearer');
      
      // Fetch and return user data along with the token
      const userData = await this.getCurrentUser();
      return { ...response.data, user: userData };
    }
    
    return response.data;
  },

  async getCurrentUser() {
    try {
      const token = this.getCurrentToken();
      const tokenType = this.getTokenType();
      const response = await axios.get(`${baseURL}/api/users/me`, {
        headers: {
          'Authorization': `${tokenType} ${token}`,
          'Content-Type': 'application/json',
        }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch user data:', error);
      return null;
    }
  },

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('token_type');
  },

  getCurrentToken() {
    return localStorage.getItem('access_token');
  },

  getTokenType() {
    return localStorage.getItem('token_type') || 'bearer';
  },

  isAuthenticated() {
    return !!localStorage.getItem('access_token');
  }
};
