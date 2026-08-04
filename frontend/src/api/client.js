import axios from 'axios'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push({ name: 'login' })
    }
    return Promise.reject(error)
  },
)

export function apiErrorMessage(error) {
  return error.response?.data?.detail ?? 'Unexpected error'
}

export default client
