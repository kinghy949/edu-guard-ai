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
        <el-menu-item v-if="!user.isStaff" index="/dashboard">
          <el-icon><Histogram /></el-icon><span>学业完成度</span>
        </el-menu-item>
        <el-menu-item index="/warnings">
          <el-icon><BellFilled /></el-icon><span>预警</span>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatLineRound /></el-icon><span>AI 学业问答</span>
        </el-menu-item>
        <el-menu-item v-if="user.isStaff" index="/admin">
          <el-icon><Tools /></el-icon><span>管理后台</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="title">{{ pageTitle }}</div>
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
import { BellFilled, ChatLineRound, DataAnalysis, Histogram, Tools, User } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const user = useUserStore()

const TITLES: Record<string, string> = {
  '/workbench': '辅导员工作台',
  '/students': '学生管理',
  '/dashboard': '学业完成度',
  '/warnings': '预警',
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
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #1f2937; color: #fff; }
.logo { color: #fff; font-size: 15px; font-weight: 600; padding: 18px 16px; letter-spacing: 0.5px; line-height: 1.4; }
:deep(.el-menu) { border-right: none; }
.header { display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #eee; }
.title { font-size: 18px; font-weight: 600; }
.user { cursor: pointer; display: inline-flex; gap: 8px; align-items: center; }
.el-main { background: #f8fafc; }
</style>
