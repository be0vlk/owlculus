import axios from 'axios'
import {authService} from './auth'

// Use relative URLs when VITE_API_BASE_URL is empty (for reverse proxy setups)
// Only fall back to localhost:8000 if the env var is not defined at all
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add a request interceptor to include the token in requests
api.interceptors.request.use(
  (config) => {
    const token = authService.getCurrentToken()
    const tokenType = authService.getTokenType()
    if (token) {
      config.headers.Authorization = `${tokenType} ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// Add a response interceptor to handle authentication errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token is invalid or expired
      authService.logout()

      // Show user notification about session expiration
      window.dispatchEvent(
        new CustomEvent('api:sessionExpired', {
          detail: { message: 'Your session has expired. Please log in again.' },
        }),
      )

      // Emit a global event for 401 errors instead of directly redirecting
      // This breaks the circular dependency with router
      window.dispatchEvent(new CustomEvent('api:unauthorized'))
    }
    return Promise.reject(error)
  },
)

export default api
