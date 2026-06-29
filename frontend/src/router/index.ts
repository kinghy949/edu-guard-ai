import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useUserStore } from '../stores/user'

const routes: RouteRecordRaw[] = [
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
      { path: 'dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'map', component: () => import('../views/AcademicMap.vue') },
      { path: 'workbench', component: () => import('../views/CounselorDashboard.vue'), meta: { staff: true } },
      { path: 'students', component: () => import('../views/Students.vue'), meta: { staff: true } },
      { path: 'students/:id', component: () => import('../views/StudentDetail.vue'), meta: { staff: true } },
      { path: 'reports', component: () => import('../views/Reports.vue'), meta: { staff: true } },
      { path: 'reports/print', component: () => import('../views/ReportPrint.vue'), meta: { staff: true } },
      { path: 'warnings', component: () => import('../views/Warnings.vue') },
      { path: 'messages', component: () => import('../views/Messages.vue') },
      { path: 'chat', component: () => import('../views/Chat.vue') },
      { path: 'admin', component: () => import('../views/Admin.vue'), meta: { staff: true } },
    ],
  },
  { path: '/:catchAll(.*)', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const store = useUserStore()
  if (to.meta.public) return true
  if (!store.isLoggedIn) return { path: '/login', query: { redirect: to.fullPath } }
  if (!store.profile) await store.fetchMe()
  // 强制改密：未改密前只允许停留在 /change-password
  if (store.profile?.must_change_password && !to.meta.allowMustChange) {
    return { path: '/change-password' }
  }
  if (to.meta.staff && !store.isStaff) return { path: '/dashboard' }
  // 根路径根据角色分流
  if (to.path === '/') {
    return { path: store.isStaff ? '/workbench' : '/dashboard' }
  }
  return true
})

export default router
