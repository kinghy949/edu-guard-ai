<template>
  <el-card>
    <template #header>
      <span>学生管理</span>
    </template>

    <el-form :model="filter" inline @submit.prevent="reload">
      <el-form-item label="关键字">
        <el-input v-model="filter.keyword" placeholder="学号 / 姓名" clearable style="width: 200px" />
      </el-form-item>
      <el-form-item label="学院"><el-input v-model="filter.college" clearable style="width: 140px" /></el-form-item>
      <el-form-item label="专业"><el-input v-model="filter.major" clearable style="width: 140px" /></el-form-item>
      <el-form-item label="班级"><el-input v-model="filter.class_name" clearable style="width: 140px" /></el-form-item>
      <el-form-item label="入学年份">
        <el-input-number v-model="filter.enroll_year" :min="2010" :max="2099" controls-position="right" style="width: 130px" />
      </el-form-item>
      <el-form-item label="预警">
        <el-select v-model="filter.warning_level" placeholder="任意" clearable style="width: 130px">
          <el-option label="severe" value="severe" />
          <el-option label="warn" value="warn" />
          <el-option label="info" value="info" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="filter.has_open_warning">仅含未处理预警</el-checkbox>
      </el-form-item>
      <el-form-item label="完成度 <">
        <el-input-number v-model="filter.completion_lt" :min="0" :max="1" :step="0.1" controls-position="right" style="width: 130px" />
      </el-form-item>
      <el-form-item label="排序">
        <el-select v-model="filter.sort" style="width: 160px">
          <el-option label="按学号" value="student_no" />
          <el-option label="完成度升序" value="completion_asc" />
          <el-option label="完成度降序" value="completion_desc" />
        </el-select>
      </el-form-item>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </el-form>

    <el-table :data="items" v-loading="loading" border style="margin-top: 12px">
      <el-table-column prop="student_no" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column label="邮箱" width="170">
        <template #default="{ row }">{{ maskEmail(row.email) }}</template>
      </el-table-column>
      <el-table-column label="手机" width="130">
        <template #default="{ row }">{{ maskPhone(row.phone) }}</template>
      </el-table-column>
      <el-table-column prop="college" label="学院" width="140" />
      <el-table-column prop="major" label="专业" width="140" />
      <el-table-column prop="class_name" label="班级" width="120" />
      <el-table-column prop="enroll_year" label="入学" width="80" />
      <el-table-column label="完成度" width="200">
        <template #default="{ row }">
          <span v-if="row.completion_ratio === null" class="muted">未刷新</span>
          <el-progress v-else :percentage="Math.round(row.completion_ratio * 100)"
                       :stroke-width="12" :status="row.completion_ratio < 0.5 ? 'exception' : ''" />
        </template>
      </el-table-column>
      <el-table-column label="未处理预警" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.open_warning_level" :type="LEVEL_TAG[row.open_warning_level]">
            {{ LEVEL_LABEL[row.open_warning_level] }}
          </el-tag>
          <span v-else class="muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button link size="small" @click="goDetail(row.id)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top: 12px"
      background layout="prev, pager, next, total"
      :current-page="page" :page-size="size" :total="total"
      @current-change="(p: number) => { page = p; load() }"
    />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { studentsApi, type StudentListItem } from '../api/endpoints'
import { maskEmail, maskPhone } from '../utils/mask'

const route = useRoute()
const router = useRouter()
const items = ref<StudentListItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)

const filter = reactive<{
  keyword?: string; college?: string; major?: string; class_name?: string;
  enroll_year?: number; warning_level?: string; has_open_warning: boolean;
  completion_lt?: number; sort: 'student_no' | 'completion_asc' | 'completion_desc';
}>({
  keyword: '', college: '', major: '', class_name: '',
  enroll_year: undefined, warning_level: undefined,
  has_open_warning: false, completion_lt: undefined, sort: 'student_no',
})

const LEVEL_LABEL: Record<string, string> = { info: '提示', warn: '警告', severe: '严重' }
const LEVEL_TAG: Record<string, 'info' | 'warning' | 'danger'> = {
  info: 'info', warn: 'warning', severe: 'danger',
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: page.value, size: size.value, sort: filter.sort,
    }
    for (const [k, v] of Object.entries(filter)) {
      if (v !== '' && v !== undefined && v !== false) params[k] = v
    }
    if (filter.has_open_warning) params.has_open_warning = true
    const data = await studentsApi.list(params)
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

function reset() {
  Object.assign(filter, {
    keyword: '', college: '', major: '', class_name: '',
    enroll_year: undefined, warning_level: undefined,
    has_open_warning: false, completion_lt: undefined, sort: 'student_no',
  })
  reload()
}

function goDetail(id: number) {
  router.push(`/students/${id}`)
}

// 从工作台跳转带来的 query
watch(
  () => route.query,
  (q) => {
    if (typeof q.class_name === 'string') filter.class_name = q.class_name
    if (typeof q.college === 'string') filter.college = q.college
  },
  { immediate: true },
)

onMounted(load)
</script>

<style scoped>
.muted { color: #94a3b8; font-size: 12px; }
</style>
