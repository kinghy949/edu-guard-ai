import axios, { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

import { useUserStore } from '../stores/user'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? '/api/v1',
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const store = useUserStore()
  if (store.token) {
    config.headers = config.headers ?? {}
    ;(config.headers as Record<string, string>).Authorization = `Bearer ${store.token}`
  }
  return config
})

http.interceptors.response.use(
  (r) => r,
  (err: AxiosError<{ detail?: string }>) => {
    const status = err.response?.status
    const msg = err.response?.data?.detail || err.message
    if (status === 401) {
      const store = useUserStore()
      store.logout()
      if (location.pathname !== '/login') {
        location.href = '/login'
      }
    } else if (status && status >= 400) {
      ElMessage.error(typeof msg === 'string' ? msg : '请求失败')
    }
    return Promise.reject(err)
  },
)

export const apiBase = (): string =>
  (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1'
