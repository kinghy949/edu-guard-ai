<template>
  <div v-loading="loading">
    <template v-if="report">
      <el-row :gutter="16" class="overview">
        <el-col :span="6">
          <el-card><div class="metric">总学分要求</div><div class="value">{{ report.total_required }}</div></el-card>
        </el-col>
        <el-col :span="6">
          <el-card><div class="metric">已修</div><div class="value text-success">{{ report.total_earned }}</div></el-card>
        </el-col>
        <el-col :span="6">
          <el-card><div class="metric">在修</div><div class="value text-info">{{ report.total_in_progress }}</div></el-card>
        </el-col>
        <el-col :span="6">
          <el-card><div class="metric">缺口</div><div class="value text-danger">{{ report.total_gap }}</div></el-card>
        </el-col>
      </el-row>

      <el-card class="block">
        <template #header>
          <span>各分类完成情况 — {{ report.program_name ?? '未关联培养方案' }}</span>
        </template>
        <el-table :data="report.buckets" border>
          <el-table-column prop="category" label="分类" width="160" />
          <el-table-column prop="required" label="要求" width="100" />
          <el-table-column prop="earned" label="已修" width="100" />
          <el-table-column prop="in_progress" label="在修" width="100" />
          <el-table-column prop="gap" label="缺口" width="100">
            <template #default="{ row }">
              <el-tag :type="Number(row.gap) > 0 ? 'danger' : 'success'" size="small">{{ row.gap }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="完成度">
            <template #default="{ row }">
              <el-progress :percentage="Math.round(row.completion_ratio * 100)" :status="row.completion_ratio >= 1 ? 'success' : row.completion_ratio < 0.5 ? 'exception' : ''" />
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="block" v-if="recommendedFlat.length">
        <template #header>推荐补修课</template>
        <el-table :data="recommendedFlat" border>
          <el-table-column prop="category" label="所属分类" width="140" />
          <el-table-column prop="code" label="课程编码" width="140" />
          <el-table-column prop="name" label="课程" />
          <el-table-column prop="credits" label="学分" width="80" />
          <el-table-column label="性质" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.is_required ? 'danger' : ''">{{ row.is_required ? '必修' : '选修' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="semester_suggested" label="建议学期" width="100" />
        </el-table>
      </el-card>

      <el-card class="block" v-if="report.failed_courses.length">
        <template #header><span class="text-danger">挂科未通过</span></template>
        <el-table :data="report.failed_courses" border>
          <el-table-column prop="code" label="课程编码" width="160" />
          <el-table-column prop="name" label="课程" />
          <el-table-column prop="credits" label="学分" width="100" />
        </el-table>
      </el-card>
    </template>
    <el-empty v-else-if="!loading" description="暂无数据，可能未关联学生记录" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { progressApi, type ProgressReport } from '../api/endpoints'
import { useUserStore } from '../stores/user'

const user = useUserStore()
const report = ref<ProgressReport | null>(null)
const loading = ref(false)

const recommendedFlat = computed(() => {
  if (!report.value) return []
  return report.value.buckets.flatMap((b) =>
    b.recommended.map((c) => ({ ...c, category: b.category })),
  )
})

onMounted(async () => {
  loading.value = true
  try {
    if (user.profile?.role === 'student') {
      report.value = await progressApi.me()
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.overview .value { font-size: 28px; font-weight: 700; }
.metric { color: #64748b; font-size: 13px; }
.block { margin-top: 16px; }
.text-success { color: #16a34a; }
.text-info { color: #2563eb; }
.text-danger { color: #dc2626; }
</style>
