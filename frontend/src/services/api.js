import axios from 'axios'
import { authService } from './auth'
import { apiBaseURL } from './config'

const api = axios.create({
  baseURL: apiBaseURL,
  headers: {
    'Content-Type': 'application/json',
  },
})

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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token is invalid or expired
      authService.logout()

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
