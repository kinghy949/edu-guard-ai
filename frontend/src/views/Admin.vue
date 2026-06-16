<template>
  <el-tabs v-model="tab">
    <!-- 导入 -->
    <el-tab-pane label="批量导入" name="imports">
      <el-row :gutter="16">
        <el-col :span="6" v-for="k in IMPORT_KINDS" :key="k.kind">
          <el-card>
            <h3>{{ k.label }}</h3>
            <p class="hint">{{ k.hint }}</p>
            <el-upload :before-upload="(file: File) => onUpload(k.kind, file)" :show-file-list="false" accept=".csv,.xlsx,.xls">
              <el-button type="primary">选择文件</el-button>
            </el-upload>
            <div v-if="results[k.kind]" class="result">
              <el-tag type="success">新建 {{ results[k.kind].created }}</el-tag>
              <el-tag style="margin-left: 6px">更新 {{ results[k.kind].updated }}</el-tag>
              <el-tag v-if="results[k.kind].errors?.length" type="danger" style="margin-left: 6px">
                错误 {{ results[k.kind].errors.length }}
              </el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card style="margin-top: 16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>导入历史</span>
            <el-button size="small" @click="loadBatches">刷新</el-button>
          </div>
        </template>
        <el-table :data="batches" border>
          <el-table-column prop="id" label="#" width="60" />
          <el-table-column prop="created_at" label="时间" width="180" />
          <el-table-column prop="kind" label="类型" width="100" />
          <el-table-column prop="filename" label="文件" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'rolled_back' ? 'danger' : 'info'">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="新建/更新/错误" width="160">
            <template #default="{ row }">{{ row.created_count }} / {{ row.updated_count }} / {{ row.error_count }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button link size="small" @click="showBatch(row.id)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          background layout="prev, pager, next, total"
          :current-page="batchPage" :page-size="batchSize" :total="batchTotal"
          @current-change="(p: number) => { batchPage = p; loadBatches() }"
          style="margin-top: 12px"
        />
      </el-card>

      <el-dialog v-model="batchDetailVisible" :title="`批次 #${batchDetail?.id}`" width="720px">
        <div v-if="batchDetail">
          <p>文件：{{ batchDetail.filename }}　类型：{{ batchDetail.kind }}　状态：{{ batchDetail.status }}</p>
          <p>新建 {{ batchDetail.created_count }}　更新 {{ batchDetail.updated_count }}　跳过 {{ batchDetail.skipped_count }}　错误 {{ batchDetail.error_count }}</p>
          <el-table v-if="batchDetail.errors?.length" :data="batchDetail.errors" border max-height="320">
            <el-table-column prop="row" label="行号" width="80" />
            <el-table-column prop="message" label="错误" />
          </el-table>
          <el-empty v-else description="本次导入无错误行" />
        </div>
      </el-dialog>
    </el-tab-pane>

    <!-- 触发预警 -->
    <el-tab-pane label="批量预警" name="warnings">
      <el-card>
        <el-form :model="gen" inline>
          <el-form-item label="学院"><el-input v-model="gen.college" /></el-form-item>
          <el-form-item label="专业"><el-input v-model="gen.major" /></el-form-item>
          <el-form-item label="入学年份"><el-input-number v-model="gen.enroll_year" :min="2010" :max="2099" /></el-form-item>
          <el-form-item label="学期"><el-input v-model="gen.semester" placeholder="如 2024-2" /></el-form-item>
          <el-form-item label="自动派发">
            <el-switch v-model="gen.auto_dispatch" />
          </el-form-item>
          <el-form-item label="渠道" v-if="gen.auto_dispatch">
            <el-checkbox-group v-model="gen.channels">
              <el-checkbox label="inbox">站内</el-checkbox>
              <el-checkbox label="email">邮件</el-checkbox>
              <el-checkbox label="wecom">企微</el-checkbox>
              <el-checkbox label="dingtalk">钉钉</el-checkbox>
              <el-checkbox label="sms">短信</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-button type="primary" @click="generate">生成</el-button>
        </el-form>
        <el-alert v-if="genResult" :title="JSON.stringify(genResult)" type="success" style="margin-top: 12px" :closable="false" />
      </el-card>
    </el-tab-pane>

    <!-- AI 模型配置 -->
    <el-tab-pane label="AI 模型" name="llm" v-if="user.isAdmin">
      <el-card>
        <p class="hint">配置对话式问答使用的 LLM。OpenAI 兼容协议，支持 DashScope / DeepSeek / GLM / 火山豆包等。<br />更新后立即生效，无需重启。api_key 留空表示不修改。</p>
        <el-form :model="llm" label-width="100px" style="max-width: 720px">
          <el-form-item label="Base URL">
            <el-input v-model="llm.base_url" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="llm.api_key" type="password" show-password :placeholder="llmCurrentKey || '尚未设置'" />
          </el-form-item>
          <el-form-item label="Model">
            <el-input v-model="llm.model" placeholder="qwen-turbo / glm-4-flash / deepseek-chat ..." />
          </el-form-item>
          <el-form-item label="Temperature">
            <el-input-number v-model="llm.temperature" :min="0" :max="2" :step="0.1" />
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="llm.enabled" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="llm.note" />
          </el-form-item>
          <el-button type="primary" @click="saveLLM">保存</el-button>
          <el-button @click="testLLM" :loading="llmTesting">测试连通</el-button>
        </el-form>
        <el-alert v-if="llmTestResult" :title="llmTestResult" type="success" style="margin-top: 12px" :closable="false" />
      </el-card>
    </el-tab-pane>

    <!-- 通知渠道配置 -->
    <el-tab-pane label="通知渠道" name="notify" v-if="user.isAdmin">
      <el-card>
        <p class="hint">为每个渠道设置开关和参数（JSON）。完整字段说明见 docs/notifications.md。</p>
        <el-table :data="configs" border>
          <el-table-column prop="channel" label="渠道" width="120" />
          <el-table-column label="启用" width="100">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="saveConfig(row)" />
            </template>
          </el-table-column>
          <el-table-column label="config (JSON)">
            <template #default="{ row }">
              <el-input v-model="row._configStr" type="textarea" :rows="2" @blur="saveConfig(row)" />
            </template>
          </el-table-column>
        </el-table>
        <el-divider />
        <h4>测试发送</h4>
        <el-form :model="testForm" inline>
          <el-form-item label="渠道">
            <el-select v-model="testForm.channel" style="width: 140px">
              <el-option v-for="c in CHANNELS" :key="c" :label="c" :value="c" />
            </el-select>
          </el-form-item>
          <el-form-item label="收件目标"><el-input v-model="testForm.target" /></el-form-item>
          <el-button @click="testSend">测试</el-button>
        </el-form>
      </el-card>
    </el-tab-pane>

    <!-- ===== 审计日志（管理员） ===== -->
    <el-tab-pane label="审计日志" name="audit" v-if="user.isAdmin">
      <el-card>
        <el-form :model="auditFilter" inline>
          <el-form-item label="动作">
            <el-input v-model="auditFilter.action" placeholder="如 auth.login.success" clearable style="width: 220px" />
          </el-form-item>
          <el-form-item label="用户ID">
            <el-input-number v-model="auditFilter.user_id" :min="0" />
          </el-form-item>
          <el-button @click="loadAudit">查询</el-button>
        </el-form>
        <el-table :data="auditRows" border style="margin-top: 12px">
          <el-table-column prop="created_at" label="时间" width="200" />
          <el-table-column prop="action" label="动作" width="220" />
          <el-table-column prop="username" label="操作人" width="120" />
          <el-table-column prop="ip" label="IP" width="140" />
          <el-table-column prop="resource_type" label="资源类型" width="120" />
          <el-table-column prop="resource_id" label="资源ID" width="120" />
          <el-table-column label="详情">
            <template #default="{ row }"><pre style="margin:0;font-size:12px">{{ JSON.stringify(row.detail, null, 2) }}</pre></template>
          </el-table-column>
        </el-table>
        <el-pagination
          background layout="prev, pager, next, total"
          :current-page="auditPage" :page-size="auditSize" :total="auditTotal"
          @current-change="(p: number) => { auditPage = p; loadAudit() }"
          style="margin-top: 12px"
        />
      </el-card>
    </el-tab-pane>
  </el-tabs>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import {
  type AuditLog, auditApi,
  type ImportBatchDetail, type ImportBatchSummary,
  importsApi, llmConfigApi, notificationsApi, warningsApi,
} from '../api/endpoints'
import { useUserStore } from '../stores/user'

const user = useUserStore()
const tab = ref('imports')

const IMPORT_KINDS = [
  { kind: 'students' as const, label: '学生名册', hint: '学号即用户名，初始密码=学号' },
  { kind: 'courses' as const, label: '课程主数据', hint: 'code/name/credits 必填' },
  { kind: 'programs' as const, label: '培养方案', hint: '每行一门课在某方案中的归属' },
  { kind: 'grades' as const, label: '成绩', hint: '按学生×课程×学期 upsert' },
]

interface ImportRes { created: number; updated: number; skipped: number; errors: { row: number; message: string }[] }
const results = reactive<Record<string, ImportRes>>({})

async function onUpload(kind: 'students' | 'courses' | 'programs' | 'grades', file: File) {
  const r = (await importsApi.upload(kind, file)) as ImportRes
  results[kind] = r
  ElMessage.success(`新建 ${r.created} / 更新 ${r.updated} / 错误 ${r.errors?.length ?? 0}`)
  loadBatches()
  return false
}

// 导入历史
const batches = ref<ImportBatchSummary[]>([])
const batchPage = ref(1)
const batchSize = ref(20)
const batchTotal = ref(0)
const batchDetail = ref<ImportBatchDetail | null>(null)
const batchDetailVisible = ref(false)

async function loadBatches() {
  const data = await importsApi.batches({ page: batchPage.value, size: batchSize.value })
  batches.value = data.items
  batchTotal.value = data.total
}

async function showBatch(id: number) {
  batchDetail.value = await importsApi.batchDetail(id)
  batchDetailVisible.value = true
}

const gen = reactive({
  college: '',
  major: '',
  enroll_year: undefined as number | undefined,
  semester: '',
  auto_dispatch: false,
  channels: ['inbox'] as string[],
})
const genResult = ref<unknown>(null)

async function generate() {
  const payload = Object.fromEntries(
    Object.entries(gen).filter(([_, v]) => v !== '' && v !== undefined && !(Array.isArray(v) && v.length === 0)),
  )
  genResult.value = await warningsApi.generate(payload as Parameters<typeof warningsApi.generate>[0])
  ElMessage.success('已生成')
}

const CHANNELS = ['inbox', 'email', 'wecom', 'dingtalk', 'sms']
interface ConfigRow { channel: string; enabled: boolean; config: Record<string, unknown> | null; _configStr: string }
const configs = ref<ConfigRow[]>([])
const testForm = reactive({ channel: 'email', target: '' })

async function loadConfigs() {
  if (!user.isAdmin) return
  const rows = (await notificationsApi.listConfigs()) as Omit<ConfigRow, '_configStr'>[]
  const byCh = new Map(rows.map((r) => [r.channel, r]))
  configs.value = CHANNELS.map((c) => {
    const row = byCh.get(c)
    return {
      channel: c,
      enabled: row?.enabled ?? false,
      config: row?.config ?? null,
      _configStr: JSON.stringify(row?.config ?? {}, null, 2),
    }
  })
}

async function saveConfig(row: ConfigRow) {
  let cfg: Record<string, unknown> = {}
  try {
    cfg = row._configStr ? JSON.parse(row._configStr) : {}
  } catch {
    ElMessage.error(`${row.channel}: JSON 格式错误`)
    return
  }
  await notificationsApi.upsertConfig(row.channel, { enabled: row.enabled, config: cfg })
  ElMessage.success(`${row.channel} 已保存`)
}

async function testSend() {
  if (!testForm.target) return ElMessage.warning('请输入目标')
  const r = await notificationsApi.test({ ...testForm })
  ElMessage.success(JSON.stringify(r))
}

const llm = reactive({
  base_url: '',
  api_key: '',
  model: '',
  temperature: 0.3,
  enabled: true,
  note: '',
})
const llmCurrentKey = ref('')
const llmTesting = ref(false)
const llmTestResult = ref('')

async function loadLLM() {
  if (!user.isAdmin) return
  const cfg = await llmConfigApi.get()
  if (cfg) {
    llm.base_url = cfg.base_url
    llm.api_key = ''
    llm.model = cfg.model
    llm.temperature = cfg.temperature
    llm.enabled = cfg.enabled
    llm.note = cfg.note ?? ''
    llmCurrentKey.value = cfg.api_key  // 脱敏值
  }
}

async function saveLLM() {
  const payload = { ...llm }
  if (!payload.api_key.trim()) delete (payload as Record<string, unknown>).api_key
  await llmConfigApi.update(payload)
  ElMessage.success('已保存')
  loadLLM()
}

async function testLLM() {
  llmTesting.value = true
  llmTestResult.value = ''
  try {
    const r = await llmConfigApi.test()
    llmTestResult.value = `回复：${r.reply}`
  } finally {
    llmTesting.value = false
  }
}

// 审计日志
const auditFilter = reactive<{ action: string; user_id: number | undefined }>({ action: '', user_id: undefined })
const auditRows = ref<AuditLog[]>([])
const auditPage = ref(1)
const auditSize = ref(20)
const auditTotal = ref(0)

async function loadAudit() {
  if (!user.isAdmin) return
  const params: { action?: string; user_id?: number; page: number; size: number } = {
    page: auditPage.value,
    size: auditSize.value,
  }
  if (auditFilter.action) params.action = auditFilter.action
  if (auditFilter.user_id) params.user_id = auditFilter.user_id
  const data = await auditApi.list(params)
  auditRows.value = data.items
  auditTotal.value = data.total
}

onMounted(() => {
  loadBatches()
  loadConfigs()
  loadLLM()
  loadAudit()
})
</script>

<style scoped>
.hint { color: #64748b; font-size: 13px; margin: 4px 0 12px; }
.result { margin-top: 10px; }
</style>
