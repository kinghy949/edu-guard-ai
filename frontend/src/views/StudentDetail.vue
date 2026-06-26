<template>
  <div v-if="student" class="detail">
    <el-page-header @back="$router.back()" :title="`返回`" :content="student.name + ' · ' + student.student_no" />

    <el-row :gutter="12" style="margin-top: 12px">
      <el-col :span="10">
        <el-card>
          <h3>基本信息</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="学号">{{ student.student_no }}</el-descriptions-item>
            <el-descriptions-item label="姓名">{{ student.name }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">
              {{ showContact ? (student.email ?? '-') : maskEmail(student.email) }}
              <el-button link size="small" @click="showContact = !showContact">
                {{ showContact ? '隐藏' : '显示' }}
              </el-button>
            </el-descriptions-item>
            <el-descriptions-item label="手机">
              {{ showContact ? (student.phone ?? '-') : maskPhone(student.phone) }}
            </el-descriptions-item>
            <el-descriptions-item label="学院">{{ student.college }}</el-descriptions-item>
            <el-descriptions-item label="专业">{{ student.major }}</el-descriptions-item>
            <el-descriptions-item label="班级">{{ student.class_name ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="入学">{{ student.enroll_year }}</el-descriptions-item>
          </el-descriptions>
          <div v-if="progress" style="margin-top: 12px">
            <h4>整体完成度</h4>
            <el-progress
              type="dashboard"
              :percentage="Math.round((Number(progress.total_earned) + Number(progress.total_in_progress)) /
                Math.max(Number(progress.total_required), 1) * 100)"
              :status="overallStatus"
            />
            <div style="margin-top: 8px; color: #64748b; font-size: 13px">
              要求 {{ progress.total_required }} · 已修 {{ progress.total_earned }} ·
              在修 {{ progress.total_in_progress }} · 缺口 {{ progress.total_gap }}
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card>
          <h3>学分桶进度</h3>
          <div v-for="b in progress?.buckets ?? []" :key="b.category" class="bucket">
            <div class="bucket-head">
              <b>{{ b.category }}</b>
              <span class="muted">{{ b.earned }} / {{ b.required }}</span>
            </div>
            <el-progress :percentage="bucketPct(b)" :status="Number(b.gap) > 0 ? 'exception' : 'success'" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 12px">
      <h3>成绩单</h3>
      <el-collapse>
        <el-collapse-item v-for="sem in transcript" :key="sem.semester" :title="sem.semester" :name="sem.semester">
          <el-table :data="sem.courses" border size="small">
            <el-table-column prop="code" label="课程编码" width="120" />
            <el-table-column prop="name" label="课程名称" />
            <el-table-column prop="credits" label="学分" width="80" />
            <el-table-column label="成绩" width="120">
              <template #default="{ row }">
                <span :class="row.status === 'failed' ? 'text-danger' : ''">
                  {{ row.score ?? '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="STATUS_TAG[row.status] ?? 'info'" size="small">
                  {{ STATUS_LABEL[row.status] ?? row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="credits_earned" label="获得学分" width="100" />
          </el-table>
        </el-collapse-item>
      </el-collapse>
      <el-empty v-if="!transcript.length" description="暂无成绩" />
    </el-card>

    <el-card style="margin-top: 12px">
      <div class="bar">
        <h3>预警历史</h3>
        <span class="muted">点击行可在新窗口处理</span>
      </div>
      <el-table :data="warnings" border>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="LEVEL_TAG[row.level]">{{ LEVEL_LABEL[row.level] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="W_STATUS_TAG[row.status] ?? 'info'" size="small">
              {{ W_STATUS_LABEL[row.status] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" />
      </el-table>
    </el-card>
  </div>
  <el-empty v-else description="加载中..." />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  progressApi, type ProgressReport, studentsApi, type StudentRead,
  type TranscriptSemester, warningsApi, type Warning,
} from '../api/endpoints'
import { maskEmail, maskPhone } from '../utils/mask'

const route = useRoute()
const id = Number(route.params.id)

const student = ref<StudentRead | null>(null)
const progress = ref<ProgressReport | null>(null)
const transcript = ref<TranscriptSemester[]>([])
const warnings = ref<Warning[]>([])
const showContact = ref(false)

const STATUS_LABEL: Record<string, string> = {
  completed: '已修', in_progress: '在修', failed: '挂科', retake: '重修',
}
const STATUS_TAG: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  completed: 'success', in_progress: 'warning', failed: 'danger', retake: 'info',
}
const LEVEL_LABEL: Record<string, string> = { info: '提示', warn: '警告', severe: '严重' }
const LEVEL_TAG: Record<string, 'info' | 'warning' | 'danger'> = {
  info: 'info', warn: 'warning', severe: 'danger',
}
const W_STATUS_LABEL: Record<string, string> = {
  open: '待处理', following: '跟进中', resolved: '已解决', ignored: '已忽略',
}
const W_STATUS_TAG: Record<string, 'warning' | 'danger' | 'success' | 'info'> = {
  open: 'warning', following: 'danger', resolved: 'success', ignored: 'info',
}

const overallStatus = computed(() => {
  if (!progress.value) return ''
  const total = Number(progress.value.total_required) || 1
  const done = (Number(progress.value.total_earned) + Number(progress.value.total_in_progress)) / total
  if (done < 0.5) return 'exception'
  if (done >= 0.95) return 'success'
  return ''
})

function bucketPct(b: { earned: string; in_progress: string; required: string }) {
  const req = Number(b.required)
  if (!req) return 100
  return Math.min(100, Math.round(((Number(b.earned) + Number(b.in_progress)) / req) * 100))
}

function formatTime(s: string) { return new Date(s).toLocaleString('zh-CN') }

onMounted(async () => {
  ;[student.value, progress.value, transcript.value, warnings.value] = await Promise.all([
    studentsApi.get(id),
    progressApi.student(id),
    studentsApi.transcript(id),
    warningsApi.list({ student_id: id }),
  ])
})
</script>

<style scoped>
.detail h3 { margin: 0 0 12px; font-size: 16px; }
.detail h4 { margin: 0 0 8px; font-size: 14px; }
.bucket { margin-bottom: 10px; }
.bucket-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.muted { color: #94a3b8; font-size: 12px; }
.bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.text-danger { color: #dc2626; }
</style>
