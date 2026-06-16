import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '../stores/user';
const routes = [
    { path: '/login', component: () => import('../views/Login.vue'), meta: { public: true } },
    {
        path: '/change-password',
        component: () => import('../views/ChangePassword.vue'),
        meta: { allowMustChange: true },
    },
    {
        path: '/',
        component: () => import('../views/Layout.vue'),
        children: [
            { path: '', redirect: '/dashboard' },
            { path: 'dashboard', component: () => import('../views/Dashboard.vue') },
            { path: 'warnings', component: () => import('../views/Warnings.vue') },
            { path: 'chat', component: () => import('../views/Chat.vue') },
            { path: 'admin', component: () => import('../views/Admin.vue'), meta: { staff: true } },
        ],
    },
    { path: '/:catchAll(.*)', redirect: '/dashboard' },
];
const router = createRouter({
    history: createWebHistory(),
    routes,
});
router.beforeEach(async (to) => {
    const store = useUserStore();
    if (to.meta.public)
        return true;
    if (!store.isLoggedIn)
        return { path: '/login', query: { redirect: to.fullPath } };
    if (!store.profile)
        await store.fetchMe();
    // 强制改密：未改密前只允许停留在 /change-password
    if (store.profile?.must_change_password && !to.meta.allowMustChange) {
        return { path: '/change-password' };
    }
    if (to.meta.staff && !store.isStaff)
        return { path: '/dashboard' };
    return true;
});
export default router;
