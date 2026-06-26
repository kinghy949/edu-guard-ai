<template>
  <el-tabs v-model="tab">
    <!-- 导入 -->
    <el-tab-pane label="批量导入" name="imports">
      <el-row :gutter="16">
        <el-col :span="6" v-for="k in IMPORT_KINDS" :key="k.kind">
          <el-card>
            <h3>{{ k.label }}</h3>
            <p class="hint">{{ k.hint }}</p>
            <el-select
              v-model="selectedMapping[k.kind]" placeholder="字段映射（可选）" clearable size="small"
              style="width: 100%; margin-bottom: 8px"
            >
              <el-option
                v-for="m in mappings.filter(x => x.kind === k.kind)" :key="m.id"
                :label="m.name" :value="m.id"
              />
            </el-select>
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
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button link size="small" @click="showBatch(row.id)">详情</el-button>
              <el-popconfirm
                v-if="user.isAdmin && row.status === 'completed'"
                :title="`确认回滚批次 #${row.id}？该操作会删除本次新建的记录、还原本次更新的字段。`"
                @confirm="rollbackBatch(row.id)"
              >
                <template #reference>
                  <el-button link size="small" type="danger">回滚</el-button>
                </template>
              </el-popconfirm>
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
          <el-button v-if="batchDetail.error_count" size="small" @click="downloadErrorReport(batchDetail.id)">
            下载错误报告 (.xlsx)
          </el-button>
          <el-table v-if="batchDetail.errors?.length" :data="batchDetail.errors" border max-height="320" style="margin-top: 12px">
            <el-table-column prop="row" label="行号" width="80" />
            <el-table-column prop="message" label="错误" />
          </el-table>
          <el-empty v-else description="本次导入无错误行" />
        </div>
      </el-dialog>

      <el-card style="margin-top: 16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>字段映射模板</span>
            <el-button size="small" type="primary" @click="openMappingForm()">新增</el-button>
          </div>
        </template>
        <el-table :data="mappings" border>
          <el-table-column prop="kind" label="类型" width="100" />
          <el-table-column prop="name" label="名称" width="200" />
          <el-table-column label="映射 (源 → 目标)">
            <template #default="{ row }">
              <pre style="margin:0;font-size:12px">{{ JSON.stringify(row.mapping, null, 2) }}</pre>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button link size="small" @click="openMappingForm(row)">编辑</el-button>
              <el-popconfirm title="确定删除？" @confirm="removeMapping(row.id)">
                <template #reference>
                  <el-button link size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-dialog v-model="mappingFormVisible" :title="mappingForm.id ? '编辑映射模板' : '新增映射模板'" width="560px">
        <el-form :model="mappingForm" label-width="80px">
          <el-form-item label="类型">
            <el-select v-model="mappingForm.kind" :disabled="!!mappingForm.id">
              <el-option label="students" value="students" />
              <el-option label="courses" value="courses" />
              <el-option label="programs" value="programs" />
              <el-option label="grades" value="grades" />
            </el-select>
          </el-form-item>
          <el-form-item label="名称">
            <el-input v-model="mappingForm.name" />
          </el-form-item>
          <el-form-item label="映射 JSON">
            <el-input v-model="mappingForm.mappingText" type="textarea" :rows="8" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="mappingFormVisible = false">取消</el-button>
          <el-button type="primary" @click="saveMapping">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="previewVisible" title="导入预检" width="640px">
        <div v-if="preview">
          <p>本次将对 <b>{{ preview.kind }}</b> 数据：</p>
          <el-tag type="success">新建 {{ preview.wouldCreate }}</el-tag>
          <el-tag type="warning" style="margin-left: 6px">更新 {{ preview.wouldUpdate }}</el-tag>
          <el-tag v-if="preview.errors.length" type="danger" style="margin-left: 6px">
            错误 {{ preview.errors.length }}
          </el-tag>
          <el-table v-if="preview.errors.length" :data="preview.errors" border max-height="280" style="margin-top: 12px">
            <el-table-column prop="row" label="行号" width="80" />
            <el-table-column prop="message" label="错误" />
          </el-table>
          <p v-if="preview.errors.length" style="color:#94a3b8;font-size:12px;margin-top:8px">
            错误行不会被导入；如需修复后重新预检，请取消并重新上传。
          </p>
        </div>
        <template #footer>
          <el-button v-if="preview?.errors.length" @click="downloadErrorReport(preview!.batchId)">下载错误报告</el-button>
          <el-button @click="previewVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="confirmImport">
            确认导入
          </el-button>
        </template>
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

      <el-card v-if="user.isAdmin" style="margin-top: 16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>定时自动预警</span>
            <el-button size="small" @click="loadJobRuns">刷新运行记录</el-button>
          </div>
        </template>
        <el-form :model="schedule" label-width="100px">
          <el-form-item label="启用">
            <el-switch v-model="schedule.enabled" />
          </el-form-item>
          <el-form-item label="cron">
            <el-input v-model="schedule.cron" placeholder="如 0 3 * * 1（每周一 3:00）" />
            <div style="color:#94a3b8;font-size:12px;margin-top:4px">五段：分 时 日 月 周</div>
          </el-form-item>
          <el-form-item label="学院">
            <el-input v-model="scheduleScopeCollege" />
          </el-form-item>
          <el-form-item label="专业">
            <el-input v-model="scheduleScopeMajor" />
          </el-form-item>
          <el-form-item label="自动派发通知">
            <el-switch v-model="schedule.auto_dispatch" />
          </el-form-item>
          <el-form-item label="渠道" v-if="schedule.auto_dispatch">
            <el-checkbox-group v-model="schedule.channels">
              <el-checkbox label="inbox">站内</el-checkbox>
              <el-checkbox label="email">邮件</el-checkbox>
              <el-checkbox label="wecom">企微</el-checkbox>
              <el-checkbox label="dingtalk">钉钉</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-button type="primary" @click="saveSchedule">保存</el-button>
          <el-button @click="runScheduleNow">立即运行一次</el-button>
        </el-form>

        <h4 style="margin-top: 16px">最近运行记录</h4>
        <el-table :data="jobRuns" border>
          <el-table-column prop="started_at" label="开始时间" width="200" />
          <el-table-column prop="job_name" label="任务" width="200" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'info'">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="结果">
            <template #default="{ row }">
              <pre style="margin:0;font-size:12px">{{ JSON.stringify(row.result, null, 2) }}</pre>
            </template>
          </el-table-column>
          <el-table-column prop="error" label="错误" width="200" />
        </el-table>
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

    <!-- ===== 预警规则（管理员） ===== -->
    <el-tab-pane label="预警规则" name="rules" v-if="user.isAdmin">
      <el-card>
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>预警规则（按 priority 倒序 + 作用域精度排序生效）</span>
            <el-button size="small" type="primary" @click="openRuleForm()">新增</el-button>
          </div>
        </template>
        <el-table :data="rules" border>
          <el-table-column prop="name" label="名称" width="160" />
          <el-table-column prop="scope_college" label="学院" width="120" />
          <el-table-column prop="scope_major" label="专业" width="120" />
          <el-table-column label="severe(总缺口/必修)" width="180">
            <template #default="{ row }">{{ row.severe_total_gap_ratio }} / {{ row.severe_required_ratio }}</template>
          </el-table-column>
          <el-table-column label="warn(总缺口/分类)" width="180">
            <template #default="{ row }">{{ row.warn_total_gap_ratio }} / {{ row.warn_category_ratio }}</template>
          </el-table-column>
          <el-table-column prop="priority" label="优先级" width="90" />
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button link size="small" @click="openRuleForm(row)">编辑</el-button>
              <el-popconfirm title="确定删除？" @confirm="removeRule(row.id)">
                <template #reference>
                  <el-button link size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-dialog v-model="ruleFormVisible" :title="ruleForm.id ? '编辑规则' : '新建规则'" width="640px">
        <el-form :model="ruleForm" label-width="160px">
          <el-form-item label="名称">
            <el-input v-model="ruleForm.name" />
          </el-form-item>
          <el-form-item label="作用学院（留空=全局）">
            <el-input v-model="ruleForm.scope_college" />
          </el-form-item>
          <el-form-item label="作用专业（留空=全局/学院）">
            <el-input v-model="ruleForm.scope_major" />
          </el-form-item>
          <el-form-item label="severe 总缺口比">
            <el-input-number v-model="ruleForm.severe_total_gap_ratio" :min="0" :max="1" :step="0.05" />
          </el-form-item>
          <el-form-item label="severe 必修完成率下限">
            <el-input-number v-model="ruleForm.severe_required_ratio" :min="0" :max="1" :step="0.05" />
          </el-form-item>
          <el-form-item label="warn 总缺口比">
            <el-input-number v-model="ruleForm.warn_total_gap_ratio" :min="0" :max="1" :step="0.05" />
          </el-form-item>
          <el-form-item label="warn 分类完成率下限">
            <el-input-number v-model="ruleForm.warn_category_ratio" :min="0" :max="1" :step="0.05" />
          </el-form-item>
          <el-form-item label="必修关键字（逗号分隔）">
            <el-input v-model="ruleForm.keywordsText" />
          </el-form-item>
          <el-form-item label="总学期数">
            <el-input-number v-model="ruleForm.stage_total_semesters" :min="1" :max="16" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="ruleForm.priority" :min="0" />
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="ruleForm.enabled" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="ruleFormVisible = false">取消</el-button>
          <el-button type="primary" @click="saveRule">保存</el-button>
        </template>
      </el-dialog>
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
            <template #default="{ row }"><pre style="margin:0;font-size:12px">{{ JSON.stringify(maskAuditDetail(row.detail), null, 2) }}</pre></template>
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
import { computed, onMounted, reactive, ref } from 'vue'

import {
  type AuditLog, auditApi,
  type ImportBatchDetail, type ImportBatchSummary,
  type ImportMapping, importMappingsApi,
  importsApi, type JobRun, llmConfigApi, notificationsApi,
  schedulerApi, warningsApi, type WarningRule, warningRulesApi,
  type WarningSchedule,
} from '../api/endpoints'
import { useUserStore } from '../stores/user'
import { maskEmail, maskPhone } from '../utils/mask'

const user = useUserStore()

function maskAuditDetail(value: unknown): unknown {
  if (Array.isArray(value)) return value.map((item) => maskAuditDetail(item))
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => {
      const lowered = key.toLowerCase()
      if (typeof item === 'string' && lowered.includes('email')) return [key, maskEmail(item)]
      if (typeof item === 'string' && (lowered.includes('phone') || lowered.includes('mobile'))) {
        return [key, maskPhone(item)]
      }
      return [key, maskAuditDetail(item)]
    }),
  )
}
const tab = ref('imports')

const IMPORT_KINDS = [
  { kind: 'students' as const, label: '学生名册', hint: '学号即用户名，初始密码=学号' },
  { kind: 'courses' as const, label: '课程主数据', hint: 'code/name/credits 必填' },
  { kind: 'programs' as const, label: '培养方案', hint: '每行一门课在某方案中的归属' },
  { kind: 'grades' as const, label: '成绩', hint: '按学生×课程×学期 upsert' },
]

interface ImportRes { created: number; updated: number; skipped: number; errors: { row: number; message: string }[] }
const results = reactive<Record<string, ImportRes>>({})

type ImportKind = 'students' | 'courses' | 'programs' | 'grades'

const preview = ref<{
  kind: ImportKind
  file: File
  batchId: number
  wouldCreate: number
  wouldUpdate: number
  errors: { row: number; message: string }[]
  mappingId?: number
} | null>(null)
const previewVisible = ref(false)
const submitting = ref(false)

const mappings = ref<ImportMapping[]>([])
const selectedMapping = reactive<Record<ImportKind, number | undefined>>({
  students: undefined, courses: undefined, programs: undefined, grades: undefined,
})

async function loadMappings() {
  mappings.value = await importMappingsApi.list()
}

async function onUpload(kind: ImportKind, file: File) {
  const mappingId = selectedMapping[kind]
  // 默认先 dry-run 预检
  const dry = await importsApi.upload(kind, file, { dryRun: true, mappingId })
  preview.value = {
    kind, file, mappingId,
    batchId: dry.batch_id,
    wouldCreate: dry.would_create ?? dry.created,
    wouldUpdate: dry.would_update ?? dry.updated,
    errors: dry.errors ?? [],
  }
  previewVisible.value = true
  loadBatches()
  return false
}

async function confirmImport() {
  if (!preview.value) return
  submitting.value = true
  try {
    const r = await importsApi.upload(preview.value.kind, preview.value.file, {
      mappingId: preview.value.mappingId,
    })
    results[preview.value.kind] = r as ImportRes
    ElMessage.success(`新建 ${r.created} / 更新 ${r.updated} / 错误 ${r.errors?.length ?? 0}`)
    previewVisible.value = false
    loadBatches()
  } finally {
    submitting.value = false
  }
}

// 字段映射模板 CRUD
const mappingForm = reactive<{ id?: number; kind: ImportKind; name: string; mappingText: string }>({
  kind: 'students', name: '', mappingText: '{\n  "学号": "student_no",\n  "姓名": "name"\n}',
})
const mappingFormVisible = ref(false)
function openMappingForm(m?: ImportMapping) {
  if (m) {
    mappingForm.id = m.id
    mappingForm.kind = m.kind as ImportKind
    mappingForm.name = m.name
    mappingForm.mappingText = JSON.stringify(m.mapping, null, 2)
  } else {
    mappingForm.id = undefined
    mappingForm.kind = 'students'
    mappingForm.name = ''
    mappingForm.mappingText = '{\n  "学号": "student_no",\n  "姓名": "name"\n}'
  }
  mappingFormVisible.value = true
}
async function saveMapping() {
  let parsed: Record<string, string>
  try {
    parsed = JSON.parse(mappingForm.mappingText)
  } catch {
    ElMessage.error('mapping JSON 解析失败')
    return
  }
  if (mappingForm.id) {
    await importMappingsApi.update(mappingForm.id, { name: mappingForm.name, mapping: parsed })
  } else {
    await importMappingsApi.create({ kind: mappingForm.kind, name: mappingForm.name, mapping: parsed })
  }
  mappingFormVisible.value = false
  ElMessage.success('已保存')
  loadMappings()
}
async function removeMapping(id: number) {
  await importMappingsApi.delete(id)
  loadMappings()
}

function downloadErrorReport(batchId: number) {
  const link = document.createElement('a')
  link.href = importsApi.errorReportUrl(batchId)
  link.download = `import_errors_batch${batchId}.xlsx`
  link.click()
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

async function rollbackBatch(id: number) {
  const res = await importsApi.rollback(id)
  ElMessage.success(`回滚完成：还原 ${res.restored} / 删除 ${res.deleted} / 跳过 ${res.skipped}`)
  loadBatches()
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

// 定时预警
const schedule = reactive<WarningSchedule>({
  enabled: false, cron: '0 3 * * 1', scope: {}, auto_dispatch: false, channels: ['inbox'],
})
const scheduleScopeCollege = computed({
  get: () => schedule.scope.college ?? '',
  set: (v: string) => { if (v) schedule.scope.college = v; else delete schedule.scope.college },
})
const scheduleScopeMajor = computed({
  get: () => schedule.scope.major ?? '',
  set: (v: string) => { if (v) schedule.scope.major = v; else delete schedule.scope.major },
})
const jobRuns = ref<JobRun[]>([])

async function loadSchedule() {
  if (!user.isAdmin) return
  Object.assign(schedule, await schedulerApi.getWarningSchedule())
}
async function loadJobRuns() {
  if (!user.isAdmin) return
  jobRuns.value = await schedulerApi.jobRuns({ limit: 20 })
}
async function saveSchedule() {
  await schedulerApi.putWarningSchedule({ ...schedule })
  ElMessage.success('已保存')
}
async function runScheduleNow() {
  const r = await schedulerApi.runWarningsNow()
  ElMessage.success(`任务 ${r.status}`)
  loadJobRuns()
}

// 预警规则
const rules = ref<WarningRule[]>([])
const ruleFormVisible = ref(false)
const ruleForm = reactive<{
  id?: number; name: string; scope_college: string; scope_major: string;
  severe_total_gap_ratio: number; warn_total_gap_ratio: number;
  severe_required_ratio: number; warn_category_ratio: number;
  keywordsText: string; stage_total_semesters: number;
  enabled: boolean; priority: number;
}>({
  name: '', scope_college: '', scope_major: '',
  severe_total_gap_ratio: 0.5, warn_total_gap_ratio: 0.25,
  severe_required_ratio: 0.5, warn_category_ratio: 0.7,
  keywordsText: '必修', stage_total_semesters: 8,
  enabled: true, priority: 0,
})

async function loadRules() {
  if (!user.isAdmin) return
  rules.value = await warningRulesApi.list()
}

function openRuleForm(r?: WarningRule) {
  if (r) {
    Object.assign(ruleForm, {
      id: r.id, name: r.name,
      scope_college: r.scope_college ?? '', scope_major: r.scope_major ?? '',
      severe_total_gap_ratio: r.severe_total_gap_ratio,
      warn_total_gap_ratio: r.warn_total_gap_ratio,
      severe_required_ratio: r.severe_required_ratio,
      warn_category_ratio: r.warn_category_ratio,
      keywordsText: (r.required_category_keywords || []).join(','),
      stage_total_semesters: r.stage_total_semesters,
      enabled: r.enabled, priority: r.priority,
    })
  } else {
    Object.assign(ruleForm, {
      id: undefined, name: '', scope_college: '', scope_major: '',
      severe_total_gap_ratio: 0.5, warn_total_gap_ratio: 0.25,
      severe_required_ratio: 0.5, warn_category_ratio: 0.7,
      keywordsText: '必修', stage_total_semesters: 8,
      enabled: true, priority: 0,
    })
  }
  ruleFormVisible.value = true
}

async function saveRule() {
  const payload = {
    name: ruleForm.name,
    scope_college: ruleForm.scope_college || null,
    scope_major: ruleForm.scope_major || null,
    severe_total_gap_ratio: ruleForm.severe_total_gap_ratio,
    warn_total_gap_ratio: ruleForm.warn_total_gap_ratio,
    severe_required_ratio: ruleForm.severe_required_ratio,
    warn_category_ratio: ruleForm.warn_category_ratio,
    required_category_keywords: ruleForm.keywordsText.split(',').map((s) => s.trim()).filter(Boolean),
    stage_total_semesters: ruleForm.stage_total_semesters,
    enabled: ruleForm.enabled,
    priority: ruleForm.priority,
  }
  if (ruleForm.id) {
    await warningRulesApi.update(ruleForm.id, payload)
  } else {
    await warningRulesApi.create(payload)
  }
  ruleFormVisible.value = false
  ElMessage.success('已保存')
  loadRules()
}

async function removeRule(id: number) {
  try {
    await warningRulesApi.delete(id)
    loadRules()
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '删除失败')
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
  loadMappings()
  loadConfigs()
  loadLLM()
  loadAudit()
  loadRules()
  loadSchedule()
  loadJobRuns()
})
</script>

<style scoped>
.hint { color: #64748b; font-size: 13px; margin: 4px 0 12px; }
.result { margin-top: 10px; }
</style>
