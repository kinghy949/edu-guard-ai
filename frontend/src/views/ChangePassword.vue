<template>
  <div class="cp-page">
    <el-card class="card">
      <div class="title">修改密码</div>
      <div class="subtitle" v-if="user.profile?.must_change_password">
        首次登录或管理员重置后，请先修改密码再使用系统
      </div>
      <el-form :model="form" @submit.prevent="submit" label-position="top">
        <el-form-item label="原密码">
          <el-input v-model="form.oldPassword" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="form.newPassword" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="form.confirm" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <div class="rule">密码要求：长度 ≥ 8，必须同时包含字母与数字，且不能与用户名/学号相同</div>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">提交</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { authApi } from '../api/endpoints'
import { useUserStore } from '../stores/user'

const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const loading = ref(false)
const user = useUserStore()
const router = useRouter()

async function submit() {
  if (!form.oldPassword || !form.newPassword) {
    ElMessage.warning('请输入原密码与新密码')
    return
  }
  if (form.newPassword !== form.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  loading.value = true
  try {
    const profile = await authApi.changePassword(form.oldPassword, form.newPassword)
    user.profile = profile
    ElMessage.success('密码已更新')
    router.push('/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.cp-page { min-height: 100vh; display: grid; place-items: center; background: #f1f5f9; }
.card { width: 420px; padding: 8px; }
.title { font-size: 22px; font-weight: 600; text-align: center; color: #1e3a8a; }
.subtitle { font-size: 13px; color: #b45309; margin: 6px 0 18px; text-align: center; }
.rule { font-size: 12px; color: #64748b; margin: -8px 0 12px; }
</style>
