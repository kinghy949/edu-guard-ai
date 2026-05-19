import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', component: () => import('../views/Login.vue') },
  { path: '/dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/warnings', component: () => import('../views/Warnings.vue') },
  { path: '/chat', component: () => import('../views/Chat.vue') },
  { path: '/admin', component: () => import('../views/Admin.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
