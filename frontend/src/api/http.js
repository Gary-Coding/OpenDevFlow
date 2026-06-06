import axios from 'axios'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

export const http = axios.create({
  baseURL: '/api/v1'
})

const pendingWrites = new Set()
const WRITE_METHODS = new Set(['post', 'put', 'patch', 'delete'])

const buildRequestKey = (config) => {
  const method = (config.method || 'get').toLowerCase()
  const url = config.url || ''
  const params = JSON.stringify(config.params || {})
  const data = typeof config.data === 'string' ? config.data : JSON.stringify(config.data || {})
  return `${method}:${url}:${params}:${data}`
}

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  const method = (config.method || 'get').toLowerCase()
  if (WRITE_METHODS.has(method)) {
    const requestKey = buildRequestKey(config)
    if (pendingWrites.has(requestKey)) {
      return Promise.reject(new axios.CanceledError('重复提交已拦截'))
    }
    pendingWrites.add(requestKey)
    config.__requestKey = requestKey
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    if (response.config.__requestKey) {
      pendingWrites.delete(response.config.__requestKey)
    }
    return response
  },
  (error) => {
    const requestKey = error.config?.__requestKey
    if (requestKey) {
      pendingWrites.delete(requestKey)
    }
    if (axios.isCancel(error)) {
      ElMessage.warning('操作处理中，请勿重复点击')
    }
    return Promise.reject(error)
  }
)
