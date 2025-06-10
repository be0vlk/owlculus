import axios from 'axios'
import { authService } from './auth'
import router from '../router'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
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

// Flag to prevent multiple simultaneous redirects
let isRedirecting = false

// Add a response interceptor to handle authentication errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token is invalid or expired
      authService.logout()
      
      // Prevent multiple simultaneous redirects
      if (!isRedirecting) {
        isRedirecting = true
        // Use Vue Router instead of window.location to avoid bypassing route guards
        router.push('/login').finally(() => {
          // Reset flag after navigation completes
          setTimeout(() => {
            isRedirecting = false
          }, 100)
        })
      }
    }
    return Promise.reject(error)
  },
)

export default api
