import axios from 'axios'

// Use relative URLs when VITE_API_BASE_URL is empty (for reverse proxy setups)
// Only fall back to localhost:8000 if the env var is not defined at all
const baseURL = import.meta.env.VITE_API_BASE_URL !== undefined 
  ? import.meta.env.VITE_API_BASE_URL 
  : 'http://localhost:8000'

// Create a separate axios instance for auth that doesn't have interceptors
// to avoid circular dependencies with the main api instance
const authApi = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const authService = {
  async login(username, password) {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)

    const response = await authApi.post('/api/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })

    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('token_type', response.data.token_type || 'bearer')

      // Fetch and return user data along with the token
      const userData = await this.getCurrentUser()
      return { ...response.data, user: userData }
    }

    return response.data
  },

  async getCurrentUser() {
    try {
      const token = this.getCurrentToken()
      const tokenType = this.getTokenType()

      if (!token) {
        throw new Error('No authentication token available')
      }

      const response = await authApi.get('/api/users/me', {
        headers: {
          Authorization: `${tokenType} ${token}`,
        },
      })
      return response.data
    } catch (error) {
      console.error('Failed to fetch user data:', error)
      // Throw the error instead of silently returning null
      // This allows calling code to handle auth failures properly
      throw error
    }
  },

  logout() {
    try {
      localStorage.removeItem('access_token')
      localStorage.removeItem('token_type')
    } catch (error) {
      console.error('Failed to clear authentication tokens:', error)
    }
  },

  getCurrentToken() {
    try {
      return localStorage.getItem('access_token')
    } catch (error) {
      console.error('Failed to retrieve access token:', error)
      return null
    }
  },

  getTokenType() {
    try {
      return localStorage.getItem('token_type') || 'bearer'
    } catch (error) {
      console.error('Failed to retrieve token type:', error)
      return 'bearer'
    }
  },

  isAuthenticated() {
    try {
      return !!localStorage.getItem('access_token')
    } catch (error) {
      console.error('Failed to check authentication status:', error)
      return false
    }
  },
}
