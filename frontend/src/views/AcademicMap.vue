<template>
  <div v-loading="loading" class="map-page">
    <template v-if="map && map.buckets.length">
      <div class="topbar">
        <div>
          <h2>{{ map.program_name || '培养方案' }}</h2>
          <div class="muted">按学分桶查看课程修读状态</div>
        </div>
        <div class="legend">
          <span v-for="item in legend" :key="item.status" class="legend-item">
            <i :class="['dot', item.status]" />{{ item.label }}
          </span>
        </div>
      </div>

      <div class="content">
        <div class="buckets">
          <section
            v-for="bucket in map.buckets"
            :key="bucket.bucket_id"
            :class="['bucket', Number(bucketGap(bucket)) > 0 ? 'needs-attention' : '']"
          >
            <div class="bucket-head">
              <div>
                <h3>{{ bucket.category }}</h3>
                <span class="muted">要求 {{ bucket.required }} 学分 · 缺口 {{ bucketGap(bucket) }}</span>
              </div>
              <el-progress
                class="bucket-progress"
                :percentage="bucketPercent(bucket)"
                :status="bucketPercent(bucket) >= 100 ? 'success' : Number(bucketGap(bucket)) > 0 ? 'exception' : ''"
              />
            </div>

            <div class="course-grid">
              <article
                v-for="course in bucket.courses"
                :key="course.id"
                :class="['course', course.status]"
              >
                <div class="course-top">
                  <span class="code">{{ course.code }}</span>
                  <el-tag size="small" :type="statusTag(course.status)">
                    {{ statusLabel[course.status] }}
                  </el-tag>
                </div>
                <div class="name">{{ course.name }}</div>
                <div class="meta">
                  <span>{{ course.credits }} 学分</span>
                  <span v-if="course.semester_suggested">建议 {{ course.semester_suggested }} 学期</span>
                  <span v-if="course.score">成绩 {{ course.score }}</span>
                </div>
                <el-tag v-if="course.is_required" size="small" type="danger" effect="plain">必修</el-tag>
              </article>
            </div>
          </section>
        </div>

        <aside class="suggestions">
          <div class="panel-title">修读建议</div>
          <template v-if="map.recommended.length">
            <div v-for="course in map.recommended" :key="`${course.bucket}-${course.id}`" class="suggestion">
              <div class="suggestion-head">
                <span>{{ course.code }}</span>
                <el-tag size="small" :type="course.is_required ? 'danger' : 'info'">
                  {{ course.is_required ? '必修' : '选修' }}
                </el-tag>
              </div>
              <div class="suggestion-name">{{ course.name }}</div>
              <div class="muted">
                {{ course.bucket }} · {{ course.credits }} 学分
                <template v-if="course.semester_suggested"> · 建议第 {{ course.semester_suggested }} 学期</template>
              </div>
            </div>
          </template>
          <el-empty v-else description="当前没有推荐补修课程" />
        </aside>
      </div>
    </template>
    <el-empty v-else-if="!loading" description="暂无学业地图，可能尚未关联培养方案" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { progressApi, type AcademicMap, type AcademicMapBucket, type CourseMapStatus } from '../api/endpoints'

const loading = ref(false)
const map = ref<AcademicMap | null>(null)

const statusLabel: Record<CourseMapStatus, string> = {
  completed: '已修',
  in_progress: '在修',
  retake: '重修',
  failed: '挂科',
  not_taken: '未修',
}

const legend = computed(() =>
  (Object.keys(statusLabel) as CourseMapStatus[]).map((status) => ({
    status,
    label: statusLabel[status],
  })),
)

function bucketEarned(bucket: AcademicMapBucket) {
  return bucket.courses
    .filter((course) => course.status === 'completed')
    .reduce((sum, course) => sum + Number(course.credits || 0), 0)
}

function bucketInProgress(bucket: AcademicMapBucket) {
  return bucket.courses
    .filter((course) => course.status === 'in_progress' || course.status === 'retake')
    .reduce((sum, course) => sum + Number(course.credits || 0), 0)
}

function bucketGap(bucket: AcademicMapBucket) {
  const gap = Math.max(Number(bucket.required || 0) - bucketEarned(bucket) - bucketInProgress(bucket), 0)
  return gap.toFixed(1).replace(/\.0$/, '')
}

function bucketPercent(bucket: AcademicMapBucket) {
  const required = Number(bucket.required || 0)
  if (!required) return 100
  return Math.min(Math.round(((bucketEarned(bucket) + bucketInProgress(bucket)) / required) * 100), 100)
}

function statusTag(status: CourseMapStatus) {
  if (status === 'completed') return 'success'
  if (status === 'in_progress' || status === 'retake') return 'primary'
  if (status === 'failed') return 'danger'
  return 'info'
}

onMounted(async () => {
  loading.value = true
  try {
    map.value = await progressApi.myMap()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.map-page { min-height: 100%; }
.topbar { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
h2, h3 { margin: 0; }
.muted { color: #64748b; font-size: 13px; }
.legend { display: flex; flex-wrap: wrap; gap: 10px 14px; font-size: 13px; color: #475569; }
.legend-item { display: inline-flex; align-items: center; gap: 6px; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.content { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 16px; align-items: start; }
.buckets { display: grid; gap: 14px; }
.bucket, .suggestions { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }
.bucket.needs-attention { border-color: #fecaca; }
.bucket-head { display: grid; grid-template-columns: minmax(0, 1fr) minmax(180px, 260px); gap: 16px; align-items: center; margin-bottom: 14px; }
.bucket-progress { width: 100%; }
.course-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; }
.course { min-height: 126px; border-radius: 8px; border: 1px solid #e5e7eb; padding: 12px; background: #f8fafc; display: flex; flex-direction: column; gap: 8px; }
.course.completed { background: #f0fdf4; border-color: #bbf7d0; }
.course.in_progress, .course.retake { background: #eff6ff; border-color: #bfdbfe; }
.course.failed { background: #fef2f2; border-color: #fecaca; }
.course.not_taken { background: #f8fafc; border-color: #e2e8f0; }
.course-top, .suggestion-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.code { color: #475569; font-size: 12px; font-weight: 700; }
.name { font-weight: 700; color: #111827; line-height: 1.35; }
.meta { display: flex; flex-wrap: wrap; gap: 6px 10px; color: #64748b; font-size: 12px; line-height: 1.4; }
.suggestions { position: sticky; top: 12px; }
.panel-title { font-weight: 700; margin-bottom: 10px; }
.suggestion { border-bottom: 1px solid #eef2f7; padding: 10px 0; }
.suggestion:first-of-type { padding-top: 0; }
.suggestion:last-child { border-bottom: 0; padding-bottom: 0; }
.suggestion-name { font-weight: 600; margin: 6px 0 4px; }

@media (max-width: 960px) {
  .content { grid-template-columns: 1fr; }
  .suggestions { position: static; }
  .bucket-head { grid-template-columns: 1fr; }
  .topbar { align-items: flex-start; flex-direction: column; }
}
</style>
