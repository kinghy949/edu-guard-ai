<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">基于AI的智能学业预警系统</div>
      <el-menu :default-active="route.path" router :collapse="false" background-color="#1f2937" text-color="#cbd5e1" active-text-color="#60a5fa">
        <el-menu-item v-if="user.isStaff" index="/workbench">
          <el-icon><DataAnalysis /></el-icon><span>工作台</span>
        </el-menu-item>
        <el-menu-item v-if="user.isStaff" index="/students">
          <el-icon><User /></el-icon><span>学生管理</span>
        </el-menu-item>
        <el-menu-item v-if="user.isStaff" index="/reports">
          <el-icon><Document /></el-icon><span>报表中心</span>
        </el-menu-item>
        <el-menu-item v-if="!user.isStaff" index="/dashboard">
          <el-icon><Histogram /></el-icon><span>学业完成度</span>
        </el-menu-item>
        <el-menu-item v-if="!user.isStaff" index="/map">
          <el-icon><Grid /></el-icon><span>学业地图</span>
        </el-menu-item>
        <el-menu-item index="/warnings">
          <el-icon><BellFilled /></el-icon><span>预警</span>
        </el-menu-item>
        <el-menu-item index="/messages">
          <el-icon><Message /></el-icon><span>消息中心</span>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatLineRound /></el-icon><span>AI 学业问答</span>
        </el-menu-item>
        <el-menu-item v-if="user.isStaff" index="/admin">
          <el-icon><Tools /></el-icon><span>管理后台</span>
        </el-menu-item>
      </el-menu>
      <div class="version">v{{ appVersion }}</div>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="title">{{ pageTitle }}</div>
        <el-badge :value="unreadCount" :hidden="!unreadCount" class="bell">
          <el-button :icon="BellFilled" circle @click="router.push('/messages')" />
        </el-badge>
        <el-dropdown>
          <span class="user">
            {{ user.profile?.display_name || user.profile?.username }}
            <el-tag size="small" :type="roleTagType">{{ roleLabel }}</el-tag>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/change-password')">修改密码</el-dropdown-item>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import {
  BellFilled,
  ChatLineRound,
  DataAnalysis,
  Document,
  Grid,
  Histogram,
  Message,
  Tools,
  User,
} from '@element-plus/icons-vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { notificationsApi } from '../api/endpoints'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const user = useUserStore()
const unreadCount = ref(0)
const appVersion = __APP_VERSION__
let unreadTimer: number | undefined

const TITLES: Record<string, string> = {
  '/workbench': '辅导员工作台',
  '/students': '学生管理',
  '/reports': '报表中心',
  '/dashboard': '学业完成度',
  '/map': '学业地图',
  '/warnings': '预警',
  '/messages': '消息中心',
  '/chat': 'AI 学业问答',
  '/admin': '管理后台',
}
const pageTitle = computed(() => TITLES[route.path] || 'EduGuard-AI')

const roleLabel = computed(() =>
  ({ admin: '管理员', counselor: '辅导员', student: '学生' })[user.profile?.role ?? 'student'],
)
const roleTagType = computed(() =>
  user.profile?.role === 'admin' ? 'danger' : user.profile?.role === 'counselor' ? 'warning' : 'info',
)

function logout() {
  user.logout()
  router.push('/login')
}

async function loadUnreadCount() {
  if (!user.isLoggedIn) return
  try {
    const data = await notificationsApi.me({ page: 1, size: 1 })
    unreadCount.value = data.unread_count
  } catch {
    // 顶栏角标不打扰主流程
  }
}

onMounted(() => {
  loadUnreadCount()
  unreadTimer = window.setInterval(loadUnreadCount, 60_000)
})

onUnmounted(() => {
  if (unreadTimer) window.clearInterval(unreadTimer)
})
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #1f2937; color: #fff; display: flex; flex-direction: column; }
.logo { color: #fff; font-size: 15px; font-weight: 600; padding: 18px 16px; letter-spacing: 0.5px; line-height: 1.4; }
:deep(.el-menu) { border-right: none; flex: 1; }
.version { color: #94a3b8; font-size: 12px; padding: 10px 16px 14px; border-top: 1px solid rgba(148, 163, 184, 0.16); }
.header { display: flex; align-items: center; justify-content: space-between; gap: 14px; background: #fff; border-bottom: 1px solid #eee; }
.title { font-size: 18px; font-weight: 600; }
.bell { margin-left: auto; }
.user { cursor: pointer; display: inline-flex; gap: 8px; align-items: center; }
.el-main { background: #f8fafc; }
</style>
