<template>
  <div class="print-page">
    <div class="header">
      <h1>{{ title }}</h1>
      <div class="meta">
        <span>生成时间：{{ now }}</span>
        <span v-if="filterText">　|　筛选：{{ filterText }}</span>
      </div>
    </div>

    <el-button class="no-print" type="primary" @click="doPrint">打印 / 保存为 PDF</el-button>

    <el-table v-if="kind === 'warnings'" :data="warnings" border style="margin-top: 12px">
      <el-table-column prop="created_at" label="时间" width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="level" label="级别" width="80" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="semester" label="学期" width="80" />
      <el-table-column prop="summary" label="摘要" />
    </el-table>

    <el-table v-if="kind === 'completion'" :data="completion" border style="margin-top: 12px">
      <el-table-column prop="student_no" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column prop="class_name" label="班级" width="120" />
      <el-table-column label="完成度">
        <template #default="{ row }">
          {{ row.completion_ratio === null ? '-' : `${Math.round(row.completion_ratio * 100)}%` }}
        </template>
      </el-table-column>
      <el-table-column prop="open_warning_level" label="最高未处理" width="120" />
    </el-table>

    <el-table v-if="kind === 'class'" :data="classRows" border style="margin-top: 12px">
      <el-table-column prop="class_name" label="班级" width="160" />
      <el-table-column prop="students" label="人数" width="100" />
      <el-table-column label="平均完成度">
        <template #default="{ row }">{{ Math.round(row.avg_completion_ratio * 100) }}%</template>
      </el-table-column>
      <el-table-column prop="open_warnings" label="未处理预警" width="120" />
      <el-table-column prop="severe_warnings" label="严重数" width="100" />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  type ClassRankingRow, statsApi, studentsApi, type StudentListItem,
  warningsApi, type Warning,
} from '../api/endpoints'

const route = useRoute()
const kind = computed(() => String(route.query.type ?? 'warnings'))
const filters = computed<Record<string, unknown>>(() => {
  try { return JSON.parse(String(route.query.filters ?? '{}')) } catch { return {} }
})

const title = computed(() => ({
  warnings: '预警明细报表',
  completion: '学业完成度报表',
  class: '班级汇总报表',
}[kind.value] ?? '报表'))

const now = new Date().toLocaleString('zh-CN')

const warnings = ref<Warning[]>([])
const completion = ref<StudentListItem[]>([])
const classRows = ref<ClassRankingRow[]>([])

const filterText = computed(() => {
  return Object.entries(filters.value).filter(([, v]) => v !== '' && v !== undefined && v !== null)
    .map(([k, v]) => `${k}=${v}`).join(' ')
})

function formatTime(s: string) { return new Date(s).toLocaleString('zh-CN') }
function doPrint() { window.print() }

onMounted(async () => {
  if (kind.value === 'warnings') {
    warnings.value = await warningsApi.list(filters.value as Record<string, string | boolean>)
  } else if (kind.value === 'completion') {
    const r = await studentsApi.list({ ...(filters.value as object), size: 500 })
    completion.value = r.items
  } else if (kind.value === 'class') {
    classRows.value = await statsApi.classRanking(filters.value as { college?: string; enroll_year?: number })
  }
})
</script>

<style scoped>
.print-page { background: #fff; padding: 16px; }
.header { margin-bottom: 12px; border-bottom: 2px solid #1f2937; padding-bottom: 8px; }
.header h1 { margin: 0; font-size: 22px; }
.header .meta { color: #64748b; font-size: 13px; margin-top: 4px; }
</style>
