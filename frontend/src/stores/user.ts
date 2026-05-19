import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: '' as string,
    profile: null as null | { id: number; name: string; role: string },
  }),
  actions: {
    setToken(t: string) {
      this.token = t
    },
    logout() {
      this.token = ''
      this.profile = null
    },
  },
})
