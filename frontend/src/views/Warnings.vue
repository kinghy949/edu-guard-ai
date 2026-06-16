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
          <el-select v-if="user.isStaff" v-model="filterStatus" placeholder="状态" clearable size="small" style="width: 120px; margin-left: 12px" @change="load">
            <el-option label="待处理" value="open" />
            <el-option label="跟进中" value="following" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已忽略" value="ignored" />
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
          <el-tag :type="STATUS_TAG[row.status] ?? 'info'" size="small">{{ STATUS_LABEL[row.status] ?? row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" link @click="openDetail(row)">详情</el-button>
          <el-button v-if="user.isStaff" size="small" link type="primary" @click="openWorkflow(row)">处理</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="detailVisible" title="预警详情" width="780px">
    <template v-if="current">
      <!-- 头部 -->
      <div class="detail-header">
        <div>
          <el-tag :type="LEVEL_TAG[current.level]" size="large">{{ LEVEL_LABEL[current.level] }}</el-tag>
          <span class="semester">学期 {{ current.semester }}</span>
        </div>
        <el-tag v-if="current.resolved_at" type="success">已处理 · {{ formatTime(current.resolved_at) }}</el-tag>
        <el-tag v-else type="warning">待处理</el-tag>
      </div>

      <p class="summary">{{ current.summary }}</p>

      <!-- 概览指标 -->
      <template v-if="detail">
        <div class="metrics">
          <div class="metric">
            <div class="label">所处学期</div>
            <div class="value">第 {{ detail.stage }} 学期</div>
          </div>
          <div class="metric">
            <div class="label">预期完成度</div>
            <div class="value">{{ pct(detail.expected_completion_ratio) }}</div>
          </div>
          <div class="metric">
            <div class="label">实际完成度</div>
            <div class="value" :class="ratioClass(detail.actual_completion_ratio, detail.expected_completion_ratio)">
              {{ pct(detail.actual_completion_ratio) }}
            </div>
          </div>
          <div class="metric">
            <div class="label">总学分要求</div>
            <div class="value">{{ detail.total_required }}</div>
          </div>
          <div class="metric">
            <div class="label">总缺口</div>
            <div class="value text-danger">{{ detail.total_gap }}</div>
          </div>
          <div class="metric" v-if="detail.failed_count">
            <div class="label">挂科门数</div>
            <div class="value text-danger">{{ detail.failed_count }}</div>
          </div>
        </div>

        <!-- 整体完成度进度条 -->
        <div class="progress-row">
          <span class="progress-label">整体完成进度</span>
          <el-progress
            :percentage="Math.round(detail.actual_completion_ratio * 100)"
            :status="detail.actual_completion_ratio < 0.5 ? 'exception' : detail.actual_completion_ratio >= 0.95 ? 'success' : ''"
            :stroke-width="14"
            style="flex: 1"
          />
        </div>
        <div class="progress-hint" v-if="detail.expected_completion_ratio">
          基于学期阶段，预期应达成 <b>{{ pct(detail.expected_completion_ratio) }}</b>
          <span v-if="detail.actual_completion_ratio < detail.expected_completion_ratio" class="text-danger">
            （落后 {{ pct(detail.expected_completion_ratio - detail.actual_completion_ratio) }}）
          </span>
        </div>

        <!-- 分类缺口 -->
        <div v-if="detail.buckets?.length" class="section">
          <h4>各分类完成情况</h4>
          <el-table :data="detail.buckets" border size="small">
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column prop="required" label="要求" width="80" />
            <el-table-column prop="earned" label="已修" width="80" />
            <el-table-column prop="in_progress" label="在修" width="80" />
            <el-table-column prop="gap" label="缺口" width="80">
              <template #default="{ row }">
                <el-tag :type="Number(row.gap) > 0 ? 'danger' : 'success'" size="small">{{ row.gap }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="完成度">
              <template #default="{ row }">
                <el-progress
                  :percentage="bucketPct(row)"
                  :status="bucketStatus(row)"
                  :stroke-width="10"
                />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>

      <p v-else class="empty">本次预警无结构化明细。</p>

      <!-- 处理备注 -->
      <div v-if="current.resolver_note" class="section">
        <h4>处理备注</h4>
        <div class="note">{{ current.resolver_note }}</div>
      </div>
    </template>
  </el-dialog>

  <!-- 处理流抽屉（仅 staff） -->
  <el-drawer v-model="workflowVisible" title="预警处理" size="520px" :destroy-on-close="true">
    <template v-if="workflowTarget">
      <p class="summary">{{ workflowTarget.summary }}</p>
      <p>
        当前状态：<el-tag :type="STATUS_TAG[workflowTarget.status] ?? 'info'">{{ STATUS_LABEL[workflowTarget.status] ?? workflowTarget.status }}</el-tag>
      </p>
      <el-form :model="actionForm" label-width="80px">
        <el-form-item label="操作">
          <el-select v-model="actionForm.action">
            <el-option v-for="opt in actionOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="actionForm.note" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
        <el-button type="primary" @click="submitAction" :loading="submittingAction">提交</el-button>
      </el-form>

      <h4 style="margin-top: 16px">跟进时间线</h4>
      <el-timeline>
        <el-timeline-item
          v-for="a in timeline" :key="a.id"
          :timestamp="formatTime(a.created_at)" placement="top"
          :type="a.action === 'resolve' ? 'success' : a.action === 'ignore' ? 'info' : 'primary'"
        >
          <div><b>{{ ACTION_LABEL[a.action] ?? a.action }}</b> · 操作人 {{ a.user_id ?? '系统' }}</div>
          <div v-if="a.note" style="color:#475569;font-size:13px;margin-top:4px">{{ a.note }}</div>
        </el-timeline-item>
        <el-empty v-if="!timeline.length" description="暂无跟进记录" />
      </el-timeline>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  warningsApi, type Warning, type WarningAction, type WarningActionType, type WarningStatus,
} from '../api/endpoints'
import { useUserStore } from '../stores/user'

interface BucketDetail {
  category: string
  required: string
  earned: string
  in_progress: string
  gap: string
}
interface WarningDetail {
  stage: number
  expected_completion_ratio: number
  actual_completion_ratio: number
  total_gap: string
  total_required: string
  buckets: BucketDetail[]
  failed_count: number
}

const user = useUserStore()
const list = ref<Warning[]>([])
const loading = ref(false)
const filterLevel = ref<string>('')
const filterStatus = ref<string>('')
const onlyOpen = ref(false)
const detailVisible = ref(false)
const current = ref<Warning | null>(null)

const LEVEL_LABEL: Record<string, string> = { info: '提示', warn: '警告', severe: '严重' }
const LEVEL_TAG: Record<string, 'info' | 'warning' | 'danger'> = {
  info: 'info', warn: 'warning', severe: 'danger',
}
const STATUS_LABEL: Record<string, string> = {
  open: '待处理', following: '跟进中', resolved: '已解决', ignored: '已忽略',
}
const STATUS_TAG: Record<string, 'info' | 'warning' | 'success' | 'danger' | ''> = {
  open: 'warning', following: 'danger', resolved: 'success', ignored: 'info',
}
const ACTION_LABEL: Record<string, string> = {
  comment: '留言', follow: '跟进', resolve: '解决', ignore: '忽略', reopen: '重开',
}

const detail = computed<WarningDetail | null>(() =>
  (current.value?.detail as unknown as WarningDetail | null) ?? null,
)

function pct(r: number | null | undefined): string {
  if (r === null || r === undefined) return '-'
  return `${Math.round(r * 100)}%`
}

function ratioClass(actual: number, expected: number): string {
  if (actual < expected * 0.7) return 'text-danger'
  if (actual < expected) return 'text-warning'
  return 'text-success'
}

function bucketPct(row: BucketDetail): number {
  const req = Number(row.required)
  if (!req) return 100
  const done = Number(row.earned) + Number(row.in_progress)
  return Math.min(100, Math.round((done / req) * 100))
}

function bucketStatus(row: BucketDetail) {
  const p = bucketPct(row)
  if (p >= 100) return 'success'
  if (p < 50) return 'exception'
  return ''
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, string | boolean> = {}
    if (filterLevel.value) params.level = filterLevel.value
    if (filterStatus.value) params.status_ = filterStatus.value
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

// 处理流抽屉
const workflowVisible = ref(false)
const workflowTarget = ref<Warning | null>(null)
const timeline = ref<WarningAction[]>([])
const submittingAction = ref(false)
const actionForm = reactive<{ action: WarningActionType; note: string }>({ action: 'follow', note: '' })

const actionOptions = computed(() => {
  const status: WarningStatus | undefined = workflowTarget.value?.status
  const all = [
    { value: 'comment' as const, label: '留言' },
    { value: 'follow' as const, label: '跟进' },
    { value: 'resolve' as const, label: '解决' },
    { value: 'ignore' as const, label: '忽略' },
    { value: 'reopen' as const, label: '重开' },
  ]
  if (status === 'open') return all.filter((o) => o.value !== 'reopen')
  if (status === 'following') return all.filter((o) => !['reopen', 'follow'].includes(o.value))
  if (status === 'resolved' || status === 'ignored') return all.filter((o) => ['comment', 'reopen'].includes(o.value))
  return all
})

async function openWorkflow(w: Warning) {
  workflowTarget.value = w
  timeline.value = await warningsApi.actions(w.id)
  actionForm.action = actionOptions.value[0]?.value ?? 'comment'
  actionForm.note = ''
  workflowVisible.value = true
}

async function submitAction() {
  if (!workflowTarget.value) return
  submittingAction.value = true
  try {
    const updated = await warningsApi.applyAction(
      workflowTarget.value.id, actionForm.action, actionForm.note || undefined,
    )
    workflowTarget.value = updated
    timeline.value = await warningsApi.actions(updated.id)
    ElMessage.success('已提交')
    actionForm.note = ''
    load()
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '操作失败')
  } finally {
    submittingAction.value = false
  }
}

function formatTime(s: string) {
  return new Date(s).toLocaleString('zh-CN')
}

onMounted(load)
</script>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; }

.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.detail-header .semester { margin-left: 12px; color: #64748b; }
.summary { font-size: 15px; color: #0f172a; padding: 10px 12px; background: #f8fafc; border-left: 3px solid #94a3b8; border-radius: 4px; margin: 0 0 16px; }

.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
.metric { background: #f8fafc; padding: 10px 14px; border-radius: 6px; }
.metric .label { font-size: 12px; color: #64748b; }
.metric .value { font-size: 20px; font-weight: 600; color: #0f172a; }

.progress-row { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.progress-label { width: 110px; color: #64748b; font-size: 13px; }
.progress-hint { font-size: 12px; color: #64748b; margin: 0 0 16px 122px; }

.section { margin-top: 16px; }
.section h4 { margin: 0 0 8px; font-size: 14px; color: #334155; }
.note { background: #f0fdf4; border-left: 3px solid #22c55e; padding: 10px 12px; border-radius: 4px; color: #14532d; }
.empty { color: #94a3b8; text-align: center; padding: 20px; }

.text-success { color: #16a34a; }
.text-warning { color: #d97706; }
.text-danger  { color: #dc2626; }
</style>
