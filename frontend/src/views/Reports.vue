<template>
  <div>
    <h2>报表中心</h2>
    <p class="hint">导出 Excel 或在浏览器打印视图中保存为 PDF。</p>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-card>
          <template #header>预警明细</template>
          <el-form :model="warn" label-width="80px" size="small">
            <el-form-item label="学期"><el-input v-model="warn.semester" placeholder="如 2024-2" clearable /></el-form-item>
            <el-form-item label="级别">
              <el-select v-model="warn.level" clearable>
                <el-option label="提示" value="info" />
                <el-option label="警告" value="warn" />
                <el-option label="严重" value="severe" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="warn.status" clearable>
                <el-option label="待处理" value="open" />
                <el-option label="跟进中" value="following" />
                <el-option label="已解决" value="resolved" />
                <el-option label="已忽略" value="ignored" />
              </el-select>
            </el-form-item>
            <el-form-item label="学院"><el-input v-model="warn.college" clearable /></el-form-item>
            <el-form-item label="班级"><el-input v-model="warn.class_name" clearable /></el-form-item>
          </el-form>
          <el-button type="primary" @click="downloadWarnings">导出 Excel</el-button>
          <el-button @click="printView('warnings')">打印视图</el-button>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card>
          <template #header>学业完成度</template>
          <el-form :model="comp" label-width="80px" size="small">
            <el-form-item label="学院"><el-input v-model="comp.college" clearable /></el-form-item>
            <el-form-item label="班级"><el-input v-model="comp.class_name" clearable /></el-form-item>
            <el-form-item label="入学年">
              <el-input-number v-model="comp.enroll_year" :min="2010" :max="2099" controls-position="right" />
            </el-form-item>
          </el-form>
          <el-button type="primary" @click="downloadCompletion">导出 Excel</el-button>
          <el-button @click="printView('completion')">打印视图</el-button>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card>
          <template #header>班级汇总</template>
          <el-form :model="cls" label-width="80px" size="small">
            <el-form-item label="学院"><el-input v-model="cls.college" clearable /></el-form-item>
            <el-form-item label="入学年">
              <el-input-number v-model="cls.enroll_year" :min="2010" :max="2099" controls-position="right" />
            </el-form-item>
          </el-form>
          <el-button type="primary" @click="downloadClass">导出 Excel</el-button>
          <el-button @click="printView('class')">打印视图</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { useRouter } from 'vue-router'

import { reportsApi } from '../api/endpoints'

const router = useRouter()

const warn = reactive<{ semester?: string; level?: string; status?: string; college?: string; class_name?: string }>({})
const comp = reactive<{ college?: string; class_name?: string; enroll_year?: number }>({})
const cls = reactive<{ college?: string; enroll_year?: number }>({})

function downloadWarnings() {
  reportsApi.download(reportsApi.warningsUrl(warn), 'warnings.xlsx')
}
function downloadCompletion() {
  reportsApi.download(reportsApi.completionUrl(comp), 'completion.xlsx')
}
function downloadClass() {
  reportsApi.download(reportsApi.classSummaryUrl(cls), 'class_summary.xlsx')
}
function printView(kind: 'warnings' | 'completion' | 'class') {
  const filters = kind === 'warnings' ? warn : kind === 'completion' ? comp : cls
  router.push({ path: '/reports/print', query: { type: kind, filters: JSON.stringify(filters) } })
}
</script>

<style scoped>
.hint { color: #94a3b8; font-size: 13px; margin: 0 0 12px; }
</style>
