<template>
  <div class="dash">
    <div class="bar">
      <h2>辅导员工作台</h2>
      <el-button type="primary" :loading="refreshing" @click="refresh">刷新快照</el-button>
    </div>

    <el-row :gutter="12">
      <el-col :span="5">
        <el-card class="metric">
          <div class="label">学生总数</div>
          <div class="value">{{ ov?.students_total ?? '-' }}</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="metric">
          <div class="label">严重未处理</div>
          <div class="value text-danger">{{ ov?.warnings_open.severe ?? '-' }}</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="metric">
          <div class="label">警告未处理</div>
          <div class="value text-warning">{{ ov?.warnings_open.warn ?? '-' }}</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="metric">
          <div class="label">平均完成度</div>
          <div class="value">{{ formatPct(ov?.avg_completion_ratio) }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="metric">
          <div class="label">挂科学生</div>
          <div class="value text-danger">{{ ov?.failed_students ?? '-' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin-top: 12px">
      <el-col :span="14">
        <el-card>
          <template #header>预警趋势（按学期）</template>
          <div ref="trendEl" style="height: 280px"></div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card>
          <template #header>预警分布（按学院）</template>
          <div ref="distEl" style="height: 280px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 12px">
      <template #header>
        <div class="bar">
          <span>班级完成度排名（升序，点击查看学生）</span>
          <span class="hint">点击柱体跳转学生列表</span>
        </div>
      </template>
      <div ref="rankEl" style="height: 320px"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  type ClassRankingRow, type DistributionRow,
  statsApi, type StatsOverview, type WarningTrendRow,
} from '../api/endpoints'

const ov = ref<StatsOverview | null>(null)
const trend = ref<WarningTrendRow[]>([])
const dist = ref<DistributionRow[]>([])
const ranking = ref<ClassRankingRow[]>([])

const trendEl = ref<HTMLDivElement | null>(null)
const distEl = ref<HTMLDivElement | null>(null)
const rankEl = ref<HTMLDivElement | null>(null)
const charts: echarts.ECharts[] = []
const refreshing = ref(false)
const router = useRouter()

function formatPct(r: number | undefined | null) {
  if (r === undefined || r === null) return '-'
  return `${Math.round(r * 100)}%`
}

async function loadAll() {
  ;[ov.value, trend.value, dist.value, ranking.value] = await Promise.all([
    statsApi.overview(),
    statsApi.warningTrend(8),
    statsApi.distribution('college'),
    statsApi.classRanking(),
  ])
  await nextTick()
  renderCharts()
}

function renderCharts() {
  charts.forEach((c) => c.dispose())
  charts.length = 0
  if (trendEl.value) {
    const c = echarts.init(trendEl.value)
    c.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['提示', '警告', '严重'] },
      xAxis: { type: 'category', data: trend.value.map((t) => t.semester) },
      yAxis: { type: 'value' },
      series: [
        { name: '提示', type: 'line', data: trend.value.map((t) => t.info), color: '#3b82f6' },
        { name: '警告', type: 'line', data: trend.value.map((t) => t.warn), color: '#f59e0b' },
        { name: '严重', type: 'line', data: trend.value.map((t) => t.severe), color: '#dc2626' },
      ],
    })
    charts.push(c)
  }
  if (distEl.value) {
    const c = echarts.init(distEl.value)
    c.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        data: dist.value.flatMap((d) => [
          { name: `${d.key}·提示`, value: d.info },
          { name: `${d.key}·警告`, value: d.warn },
          { name: `${d.key}·严重`, value: d.severe },
        ]).filter((x) => x.value > 0),
      }],
    })
    charts.push(c)
  }
  if (rankEl.value) {
    const c = echarts.init(rankEl.value)
    c.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 100 },
      xAxis: { type: 'value', max: 1, axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` } },
      yAxis: {
        type: 'category', data: ranking.value.map((r) => r.class_name),
      },
      series: [{
        type: 'bar',
        data: ranking.value.map((r) => r.avg_completion_ratio),
        itemStyle: { color: '#22c55e' },
        label: { show: true, position: 'right', formatter: (p: { value: number }) => `${Math.round(p.value * 100)}%` },
      }],
    })
    c.on('click', (p: { name?: string }) => {
      if (p.name) router.push({ path: '/students', query: { class_name: p.name } })
    })
    charts.push(c)
  }
}

async function refresh() {
  refreshing.value = true
  try {
    const r = await statsApi.refreshSnapshots()
    ElMessage.success(`已刷新 ${r.refreshed} 个学生快照`)
    loadAll()
  } finally {
    refreshing.value = false
  }
}

onMounted(loadAll)
onBeforeUnmount(() => charts.forEach((c) => c.dispose()))
</script>

<style scoped>
.dash { padding: 4px; }
.bar { display: flex; justify-content: space-between; align-items: center; }
.metric { text-align: center; }
.metric .label { color: #64748b; font-size: 13px; }
.metric .value { font-size: 28px; font-weight: 700; color: #0f172a; }
.text-warning { color: #d97706; }
.text-danger { color: #dc2626; }
.hint { font-size: 12px; color: #94a3b8; }
</style>
