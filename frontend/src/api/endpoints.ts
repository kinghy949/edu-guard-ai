import { http } from './index'

export interface User {
  id: number
  username: string
  role: 'student' | 'counselor' | 'admin'
  email: string | null
  phone: string | null
  display_name: string | null
  is_active: boolean
  must_change_password?: boolean
}

export interface BucketProgress {
  bucket_id: number | null
  category: string
  required: string
  earned: string
  in_progress: string
  gap: string
  completion_ratio: number
  recommended: {
    id: number
    code: string
    name: string
    credits: string
    is_required: boolean
    semester_suggested: number | null
  }[]
}

export interface ProgressReport {
  student_id: number
  student_no: string
  student_name: string
  program_id: number | null
  program_name: string | null
  total_required: string
  total_earned: string
  total_in_progress: string
  total_gap: string
  buckets: BucketProgress[]
  failed_courses: { id: number; code: string; name: string; credits: string }[]
}

export type WarningStatus = 'open' | 'following' | 'resolved' | 'ignored'
export type WarningActionType = 'comment' | 'follow' | 'resolve' | 'ignore' | 'reopen'

export interface Warning {
  id: number
  student_id: number
  level: 'info' | 'warn' | 'severe'
  semester: string
  summary: string
  detail: Record<string, unknown> | null
  resolved_at: string | null
  resolver_note: string | null
  status: WarningStatus
  assignee_id: number | null
  created_at: string
  updated_at: string
}

export interface WarningAction {
  id: number
  warning_id: number
  user_id: number | null
  action: WarningActionType
  note: string | null
  created_at: string
}

export interface ChatSession {
  id: number
  user_id: number
  title: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: number
  session_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
  updated_at: string
}

export const authApi = {
  async login(
    username: string,
    password: string,
  ): Promise<{ token: string; mustChangePassword: boolean }> {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    const r = await http.post<{ access_token: string; must_change_password?: boolean }>(
      '/auth/login',
      form,
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
    )
    return {
      token: r.data.access_token,
      mustChangePassword: !!r.data.must_change_password,
    }
  },
  me: () => http.get<User>('/auth/me').then((r) => r.data),
  changePassword: (oldPassword: string, newPassword: string) =>
    http
      .post<User>('/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      })
      .then((r) => r.data),
}

export const progressApi = {
  me: () => http.get<ProgressReport>('/progress/me').then((r) => r.data),
  student: (id: number) =>
    http.get<ProgressReport>(`/progress/${id}`).then((r) => r.data),
}

export const warningsApi = {
  list: (params?: Record<string, string | number | boolean>) =>
    http.get<Warning[]>('/warnings', { params }).then((r) => r.data),
  get: (id: number) => http.get<Warning>(`/warnings/${id}`).then((r) => r.data),
  generate: (payload: {
    student_ids?: number[]
    semester?: string
    college?: string
    major?: string
    enroll_year?: number
    auto_dispatch?: boolean
    channels?: string[]
  }) => http.post('/warnings/generate', payload).then((r) => r.data),
  resolve: (id: number, note?: string) =>
    http.post(`/warnings/${id}/resolve`, { note }).then((r) => r.data),
  actions: (id: number) =>
    http.get<WarningAction[]>(`/warnings/${id}/actions`).then((r) => r.data),
  applyAction: (id: number, action: WarningActionType, note?: string) =>
    http.post<Warning>(`/warnings/${id}/actions`, { action, note }).then((r) => r.data),
}

export const chatApi = {
  sessions: () => http.get<ChatSession[]>('/chat/sessions').then((r) => r.data),
  createSession: (title?: string) =>
    http.post<ChatSession>('/chat/sessions', { title }).then((r) => r.data),
  messages: (sessionId: number) =>
    http
      .get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`)
      .then((r) => r.data),
  send: (sessionId: number, content: string) =>
    http
      .post<ChatMessage>(`/chat/sessions/${sessionId}/messages`, { content })
      .then((r) => r.data),
  deleteSession: (id: number) => http.delete(`/chat/sessions/${id}`),
}

export interface ImportBatchSummary {
  id: number
  kind: string
  filename: string | null
  status: string
  dry_run: boolean
  total_rows: number
  created_count: number
  updated_count: number
  skipped_count: number
  error_count: number
  operator_id: number | null
  created_at: string
}

export interface ImportBatchDetail extends ImportBatchSummary {
  errors: { row: number; message: string }[] | null
  mapping: Record<string, string> | null
}

export const importsApi = {
  templates: () => http.get('/imports/templates').then((r) => r.data),
  upload: (
    kind: 'students' | 'courses' | 'programs' | 'grades',
    file: File,
    opts: { dryRun?: boolean; mappingId?: number } = {},
  ) => {
    const fd = new FormData()
    fd.append('file', file)
    if (opts.mappingId) fd.append('mapping_id', String(opts.mappingId))
    return http
      .post<{
        batch_id: number; status: string; dry_run: boolean;
        created: number; updated: number; skipped: number;
        would_create?: number; would_update?: number;
        errors: { row: number; message: string }[]
      }>(`/imports/${kind}`, fd, {
        params: opts.dryRun ? { dry_run: true } : undefined,
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
  batches: (params?: { kind?: string; page?: number; size?: number }) =>
    http.get<{ items: ImportBatchSummary[]; total: number }>('/imports/batches', { params }).then((r) => r.data),
  batchDetail: (id: number) => http.get<ImportBatchDetail>(`/imports/batches/${id}`).then((r) => r.data),
  errorReportUrl: (batchId: number) => `/api/v1/imports/batches/${batchId}/errors.xlsx`,
  rollback: (batchId: number) =>
    http.post<{ restored: number; deleted: number; skipped: number; skipped_details: { row: number; reason: string }[] }>(
      `/imports/batches/${batchId}/rollback`,
    ).then((r) => r.data),
}

export interface ImportMapping {
  id: number
  kind: string
  name: string
  mapping: Record<string, string>
  is_default: boolean
  created_by: number | null
  created_at: string
  updated_at: string
}

export interface WarningSchedule {
  enabled: boolean
  cron: string
  scope: { college?: string; major?: string; enroll_year?: number; semester?: string }
  auto_dispatch: boolean
  channels: string[]
}

export interface JobRun {
  id: number
  job_name: string
  status: string
  started_at: string
  finished_at: string | null
  result: Record<string, unknown> | null
  error: string | null
}

export const schedulerApi = {
  getWarningSchedule: () => http.get<WarningSchedule>('/admin/settings/warning-schedule').then((r) => r.data),
  putWarningSchedule: (payload: WarningSchedule) =>
    http.put<WarningSchedule>('/admin/settings/warning-schedule', payload).then((r) => r.data),
  jobRuns: (params?: { job_name?: string; limit?: number }) =>
    http.get<JobRun[]>('/admin/job-runs', { params }).then((r) => r.data),
  runWarningsNow: () =>
    http.post<{ status: string; result?: Record<string, unknown> }>('/admin/jobs/generate-warnings/run-now').then((r) => r.data),
}

export interface WarningRule {
  id: number
  name: string
  scope_college: string | null
  scope_major: string | null
  severe_total_gap_ratio: number
  warn_total_gap_ratio: number
  severe_required_ratio: number
  warn_category_ratio: number
  required_category_keywords: string[]
  stage_total_semesters: number
  enabled: boolean
  priority: number
  updated_by: number | null
  created_at: string
  updated_at: string
}

export const warningRulesApi = {
  list: () => http.get<WarningRule[]>('/admin/warning-rules').then((r) => r.data),
  create: (payload: Partial<Omit<WarningRule, 'id' | 'updated_by' | 'created_at' | 'updated_at'>>) =>
    http.post<WarningRule>('/admin/warning-rules', payload).then((r) => r.data),
  update: (id: number, payload: Partial<Omit<WarningRule, 'id' | 'updated_by' | 'created_at' | 'updated_at'>>) =>
    http.patch<WarningRule>(`/admin/warning-rules/${id}`, payload).then((r) => r.data),
  delete: (id: number) => http.delete(`/admin/warning-rules/${id}`).then((r) => r.data),
}

export interface StatsOverview {
  students_total: number
  warnings_open: { info: number; warn: number; severe: number }
  warnings_resolved_ratio: number
  avg_completion_ratio: number
  failed_students: number
}

export interface ClassRankingRow {
  class_name: string
  students: number
  avg_completion_ratio: number
  open_warnings: number
  severe_warnings: number
}

export interface DistributionRow {
  key: string
  info: number
  warn: number
  severe: number
}

export interface WarningTrendRow {
  semester: string
  info: number
  warn: number
  severe: number
}

export interface StudentRead {
  id: number
  user_id: number
  student_no: string
  name: string
  gender: string | null
  enroll_year: number
  college: string
  major: string
  class_name: string | null
  program_id: number | null
}

export interface StudentListItem extends StudentRead {
  completion_ratio: number | null
  open_warning_level: 'info' | 'warn' | 'severe' | null
}

export interface TranscriptCourse {
  code: string
  name: string
  credits: string
  credits_earned: string
  score: string | null
  status: string
  semester: string
}
export interface TranscriptSemester {
  semester: string
  courses: TranscriptCourse[]
}

export const studentsApi = {
  list: (params?: {
    page?: number; size?: number; keyword?: string;
    college?: string; major?: string; class_name?: string; enroll_year?: number;
    has_open_warning?: boolean; warning_level?: string;
    completion_lt?: number; sort?: 'student_no' | 'completion_asc' | 'completion_desc';
  }) => http.get<{ items: StudentListItem[]; total: number }>('/students', { params }).then((r) => r.data),
  get: (id: number) => http.get<StudentRead>(`/students/${id}`).then((r) => r.data),
  transcript: (id: number) => http.get<TranscriptSemester[]>(`/students/${id}/transcript`).then((r) => r.data),
}

export const reportsApi = {
  warningsUrl: (params: Record<string, string | number | undefined>) =>
    `/api/v1/reports/warnings.xlsx?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v !== undefined) as [string, string][],
    )}`,
  completionUrl: (params: Record<string, string | number | undefined>) =>
    `/api/v1/reports/completion.xlsx?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v !== undefined) as [string, string][],
    )}`,
  classSummaryUrl: (params: Record<string, string | number | undefined>) =>
    `/api/v1/reports/class-summary.xlsx?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v !== undefined) as [string, string][],
    )}`,
  download: async (url: string, filename: string) => {
    const r = await http.get(url.replace('/api/v1', ''), { responseType: 'blob' })
    const blob = new Blob([r.data])
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    link.click()
    URL.revokeObjectURL(link.href)
  },
}

export const statsApi = {
  overview: (college?: string) =>
    http.get<StatsOverview>('/stats/overview', { params: college ? { college } : undefined }).then((r) => r.data),
  warningTrend: (semesters = 6) =>
    http.get<WarningTrendRow[]>('/stats/warning-trend', { params: { semesters } }).then((r) => r.data),
  classRanking: (params?: { college?: string; enroll_year?: number }) =>
    http.get<ClassRankingRow[]>('/stats/class-ranking', { params }).then((r) => r.data),
  distribution: (dim: 'college' | 'major' | 'class_name' = 'college') =>
    http.get<DistributionRow[]>('/stats/distribution', { params: { dim } }).then((r) => r.data),
  refreshSnapshots: () =>
    http.post<{ refreshed: number }>('/stats/refresh-snapshots').then((r) => r.data),
}

export const importMappingsApi = {
  list: (kind?: string) =>
    http.get<ImportMapping[]>('/imports/mappings', { params: kind ? { kind } : undefined }).then((r) => r.data),
  create: (payload: { kind: string; name: string; mapping: Record<string, string>; is_default?: boolean }) =>
    http.post<ImportMapping>('/imports/mappings', payload).then((r) => r.data),
  update: (id: number, payload: { name?: string; mapping?: Record<string, string>; is_default?: boolean }) =>
    http.put<ImportMapping>(`/imports/mappings/${id}`, payload).then((r) => r.data),
  delete: (id: number) => http.delete(`/imports/mappings/${id}`).then((r) => r.data),
}

export interface LLMConfig {
  id: number
  base_url: string
  api_key: string
  model: string
  temperature: number
  enabled: boolean
  note: string | null
  updated_by: number | null
  created_at: string
  updated_at: string
}

export const llmConfigApi = {
  get: () => http.get<LLMConfig | null>('/admin/llm-config').then((r) => r.data),
  update: (payload: Partial<Omit<LLMConfig, 'id' | 'created_at' | 'updated_at' | 'updated_by'>>) =>
    http.put<LLMConfig>('/admin/llm-config', payload).then((r) => r.data),
  test: (prompt = '你好，请用一句话介绍你自己。') =>
    http.post<{ ok: boolean; reply: string }>('/admin/llm-config/test', { prompt }).then((r) => r.data),
}

export interface AuditLog {
  id: number
  user_id: number | null
  username: string | null
  action: string
  resource_type: string | null
  resource_id: string | null
  detail: Record<string, unknown> | null
  ip: string | null
  created_at: string
}

export const auditApi = {
  list: (params?: { action?: string; user_id?: number; page?: number; size?: number }) =>
    http.get<{ items: AuditLog[]; total: number }>('/admin/audit-logs', { params }).then((r) => r.data),
}

export const notificationsApi = {
  listConfigs: () =>
    http.get('/notifications/configs/all').then((r) => r.data),
  upsertConfig: (
    channel: string,
    payload: { enabled?: boolean; config?: Record<string, unknown> },
  ) =>
    http
      .put(`/notifications/configs/${channel}`, payload)
      .then((r) => r.data),
  test: (payload: {
    channel: string
    target: string
    subject?: string
    content?: string
  }) => http.post('/notifications/test', payload).then((r) => r.data),
}
