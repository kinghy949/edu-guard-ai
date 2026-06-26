<template>
  <el-card>
    <template #header>
      <div class="bar">
        <div>
          <span>消息中心</span>
          <el-tag v-if="unreadCount" size="small" type="danger" style="margin-left: 8px">
            未读 {{ unreadCount }}
          </el-tag>
        </div>
        <div class="actions">
          <el-checkbox v-model="unreadOnly" @change="reload">仅未读</el-checkbox>
          <el-button size="small" @click="load">刷新</el-button>
          <el-button size="small" type="primary" :disabled="!unreadCount" @click="readAll">全部已读</el-button>
        </div>
      </div>
    </template>

    <el-table :data="items" v-loading="loading" border @row-click="openMessage">
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.read_at ? 'info' : 'danger'">
            {{ row.read_at ? '已读' : '未读' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="主题">
        <template #default="{ row }">
          <span :class="{ unread: !row.read_at }">{{ row.subject || '站内通知' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.warning_id" link size="small" @click.stop="router.push('/warnings')">查看预警</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      background
      layout="prev, pager, next, total"
      :current-page="page"
      :page-size="size"
      :total="total"
      @current-change="(p: number) => { page = p; load() }"
      style="margin-top: 12px"
    />
  </el-card>

  <el-dialog v-model="dialogVisible" title="消息详情" width="640px">
    <template v-if="current">
      <h3>{{ current.subject || '站内通知' }}</h3>
      <p class="time">{{ formatTime(current.created_at) }}</p>
      <div class="content">{{ current.content || '无内容' }}</div>
    </template>
    <template #footer>
      <el-button v-if="current?.warning_id" type="primary" @click="router.push('/warnings')">查看预警</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { notificationsApi, type InboxNotification } from '../api/endpoints'

const router = useRouter()
const items = ref<InboxNotification[]>([])
const total = ref(0)
const unreadCount = ref(0)
const unreadOnly = ref(false)
const page = ref(1)
const size = 20
const loading = ref(false)
const dialogVisible = ref(false)
const current = ref<InboxNotification | null>(null)

function formatTime(v: string | null) {
  return v ? new Date(v).toLocaleString() : '-'
}

async function load() {
  loading.value = true
  try {
    const data = await notificationsApi.me({
      unread_only: unreadOnly.value || undefined,
      page: page.value,
      size,
    })
    items.value = data.items
    total.value = data.total
    unreadCount.value = data.unread_count
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

async function openMessage(row: InboxNotification) {
  current.value = row
  dialogVisible.value = true
  if (!row.read_at) {
    const updated = await notificationsApi.markRead(row.id)
    row.read_at = updated.read_at
    unreadCount.value = Math.max(unreadCount.value - 1, 0)
  }
}

async function readAll() {
  const r = await notificationsApi.readAll()
  ElMessage.success(`已标记 ${r.updated} 条消息`)
  await load()
}

onMounted(load)
</script>

<style scoped>
.bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.actions { display: inline-flex; align-items: center; gap: 10px; }
.unread { font-weight: 700; color: #111827; }
.time { color: #64748b; font-size: 13px; margin: 4px 0 16px; }
.content { white-space: pre-wrap; line-height: 1.7; color: #111827; }
</style>
