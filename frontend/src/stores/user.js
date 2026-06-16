import { defineStore } from 'pinia';
import { authApi } from '../api/endpoints';
const TOKEN_KEY = 'eduguard.token';
export const useUserStore = defineStore('user', {
    state: () => ({
        token: localStorage.getItem(TOKEN_KEY) ?? '',
        profile: null,
    }),
    getters: {
        isLoggedIn: (s) => !!s.token,
        isStaff: (s) => s.profile?.role === 'admin' || s.profile?.role === 'counselor',
        isAdmin: (s) => s.profile?.role === 'admin',
    },
    actions: {
        setToken(t) {
            this.token = t;
            if (t)
                localStorage.setItem(TOKEN_KEY, t);
            else
                localStorage.removeItem(TOKEN_KEY);
        },
        async login(username, password) {
            const { token } = await authApi.login(username, password);
            this.setToken(token);
            await this.fetchMe();
        },
        async fetchMe() {
            if (!this.token)
                return;
            try {
                this.profile = await authApi.me();
            }
            catch {
                this.logout();
            }
        },
        logout() {
            this.setToken('');
            this.profile = null;
        },
    },
});
