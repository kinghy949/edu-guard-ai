<template>
  <el-card>
    <template #header>
      <div class="bar">
        <span>预警列表</span>
        <div>
          <el-select v-model="filterLevel" placeholder="级别" clearable size="small" style="width: 120px" @change="load">
            <el-option label="提示" value="info" />
            <el-option label="警告" value="warn" />
            <el-option label="严重" value="severe" />
          </el-select>
          <el-checkbox v-model="onlyOpen" @change="load" style="margin-left: 12px">仅未处理</el-checkbox>
        </div>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" border>
      <el-table-column prop="semester" label="学期" width="120" />
      <el-table-column prop="level" label="级别" width="100">
        <template #default="{ row }">
          <el-tag :type="LEVEL_TAG[row.level]" size="small">{{ LEVEL_LABEL[row.level] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="summary" label="摘要" />
      <el-table-column prop="created_at" label="生成时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.resolved_at" type="success" size="small">已处理</el-tag>
          <el-tag v-else type="warning" size="small">待处理</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button size="small" link @click="openDetail(row)">详情</el-button>
          <el-button v-if="!row.resolved_at && user.isStaff" size="small" link type="success" @click="resolve(row)">标记处理</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="detailVisible" title="预警详情" width="640px">
    <template v-if="current">
      <p><b>学期：</b>{{ current.semester }}</p>
      <p><b>级别：</b><el-tag :type="LEVEL_TAG[current.level]">{{ LEVEL_LABEL[current.level] }}</el-tag></p>
      <p><b>摘要：</b>{{ current.summary }}</p>
      <el-divider />
      <pre class="detail">{{ JSON.stringify(current.detail, null, 2) }}</pre>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

import { warningsApi, type Warning } from '../api/endpoints'
import { useUserStore } from '../stores/user'

const user = useUserStore()
const list = ref<Warning[]>([])
const loading = ref(false)
const filterLevel = ref<string>('')
const onlyOpen = ref(false)
const detailVisible = ref(false)
const current = ref<Warning | null>(null)

const LEVEL_LABEL: Record<string, string> = { info: '提示', warn: '警告', severe: '严重' }
const LEVEL_TAG: Record<string, 'info' | 'warning' | 'danger'> = {
  info: 'info', warn: 'warning', severe: 'danger',
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, string | boolean> = {}
    if (filterLevel.value) params.level = filterLevel.value
    if (onlyOpen.value) params.only_open = true
    list.value = await warningsApi.list(params)
  } finally {
    loading.value = false
  }
}

function openDetail(w: Warning) {
  current.value = w
  detailVisible.value = true
}

async function resolve(w: Warning) {
  const { value } = await ElMessageBox.prompt('处理备注（可选）', '标记处理', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
  }).catch(() => ({ value: undefined }))
  if (value === undefined) return
  await warningsApi.resolve(w.id, value || undefined)
  ElMessage.success('已标记处理')
  load()
}

function formatTime(s: string) {
  return new Date(s).toLocaleString('zh-CN')
}

onMounted(load)
</script>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; }
.detail { background: #f8fafc; padding: 12px; border-radius: 4px; max-height: 400px; overflow: auto; }
</style>
