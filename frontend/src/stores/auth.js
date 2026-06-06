import { defineStore } from 'pinia'
import { http } from '../api/http'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    isAdmin: (state) => state.user?.roles?.includes('admin'),
    hasPermission: (state) => (code) => {
      const permissions = state.user?.permissions || []
      if (permissions.includes('*:*:*') || permissions.includes(code)) return true
      const [module, resource, action] = code.split(':')
      return permissions.includes(`${module}:*:*`) ||
        permissions.includes(`${module}:${resource}:*`) ||
        permissions.includes(`*:*:${action}`)
    }
  },
  actions: {
    async login(username, password) {
      const { data } = await http.post('/auth/login', { username, password })
      this.token = data.access_token
      localStorage.setItem('token', this.token)
      await this.loadMe()
    },
    async loadMe() {
      if (!this.token) return
      const { data } = await http.get('/auth/me')
      this.user = data
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
    }
  }
})
