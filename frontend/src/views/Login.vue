<template>
  <div class="login-page">
    <el-card class="card">
      <div class="brand">EduGuard-AI</div>
      <div class="subtitle">智能学业预警系统</div>
      <el-form :model="form" @submit.prevent="submit" label-position="top">
        <el-form-item label="用户名 / 学号">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">登录</el-button>
      </el-form>
      <div class="hint">首次登录的学生账户：用户名 = 学号，初始密码 = 学号</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useUserStore } from '../stores/user'

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const user = useUserStore()
const router = useRouter()
const route = useRoute()

async function submit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名与密码')
    return
  }
  loading.value = true
  try {
    await user.login(form.username, form.password)
    if (user.profile?.must_change_password) {
      ElMessage.warning('为保障账号安全，请先修改初始密码')
      router.push('/change-password')
      return
    }
    const fallback = user.isStaff ? '/workbench' : '/dashboard'
    const redirect = (route.query.redirect as string) || fallback
    router.push(redirect)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { min-height: 100vh; display: grid; place-items: center; background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); }
.card { width: 380px; padding: 8px; }
.brand { font-size: 28px; font-weight: 700; text-align: center; color: #1e3a8a; }
.subtitle { font-size: 14px; text-align: center; color: #64748b; margin: 4px 0 24px; }
.hint { font-size: 12px; color: #94a3b8; margin-top: 12px; text-align: center; }
</style>
