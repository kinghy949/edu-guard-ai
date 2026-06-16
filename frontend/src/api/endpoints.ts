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

export interface Warning {
  id: number
  student_id: number
  level: 'info' | 'warn' | 'severe'
  semester: string
  summary: string
  detail: Record<string, unknown> | null
  resolved_at: string | null
  resolver_note: string | null
  created_at: string
  updated_at: string
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

export const importsApi = {
  templates: () => http.get('/imports/templates').then((r) => r.data),
  upload: (kind: 'students' | 'courses' | 'programs' | 'grades', file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return http
      .post(`/imports/${kind}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
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
