<template>
  <div class="chat-wrap">
    <el-card class="sidebar">
      <template #header>
        <div class="bar">
          <span>会话</span>
          <el-button size="small" type="primary" @click="newSession">新建</el-button>
        </div>
      </template>
      <ul class="sessions">
        <li
          v-for="s in sessions"
          :key="s.id"
          :class="{ active: current?.id === s.id }"
          @click="select(s.id)"
        >
          <span class="title">{{ s.title || '新会话' }}</span>
          <el-icon class="del" @click.stop="remove(s.id)"><Delete /></el-icon>
        </li>
      </ul>
    </el-card>

    <el-card class="conversation">
      <template #header>
        <span>{{ current?.title || '请选择或新建会话' }}</span>
      </template>

      <div class="messages" ref="msgsEl">
        <div v-for="m in messages" :key="m.id || m.content" :class="['msg', m.role]">
          <div class="role">{{ m.role === 'user' ? '我' : 'AI 助手' }}</div>
          <div class="bubble">{{ m.content }}</div>
        </div>
        <div v-if="streaming" class="msg assistant">
          <div class="role">AI 助手</div>
          <div class="bubble">{{ streamingText }}<span class="cursor">▍</span></div>
        </div>
      </div>

      <div class="composer">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          placeholder="问我「我还差什么没修？」「下学期建议选什么？」"
          @keydown.enter.exact.prevent="send"
        />
        <el-button type="primary" :loading="streaming" :disabled="!current" @click="send">发送</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { nextTick, onMounted, ref } from 'vue'

import { apiBase } from '../api'
import { chatApi, type ChatMessage, type ChatSession } from '../api/endpoints'
import { useUserStore } from '../stores/user'

const user = useUserStore()
const sessions = ref<ChatSession[]>([])
const current = ref<ChatSession | null>(null)
const messages = ref<ChatMessage[]>([])
const input = ref('')
const streaming = ref(false)
const streamingText = ref('')
const msgsEl = ref<HTMLDivElement | null>(null)

async function loadSessions() {
  sessions.value = await chatApi.sessions()
  if (sessions.value.length && !current.value) {
    await select(sessions.value[0].id)
  }
}

async function newSession() {
  const s = await chatApi.createSession()
  sessions.value.unshift(s)
  await select(s.id)
}

async function select(id: number) {
  current.value = sessions.value.find((s) => s.id === id) ?? null
  messages.value = await chatApi.messages(id)
  scrollBottom()
}

async function remove(id: number) {
  await ElMessageBox.confirm('确认删除该会话？', '提示', { type: 'warning' })
  await chatApi.deleteSession(id)
  sessions.value = sessions.value.filter((s) => s.id !== id)
  if (current.value?.id === id) {
    current.value = null
    messages.value = []
  }
}

function scrollBottom() {
  nextTick(() => {
    if (msgsEl.value) msgsEl.value.scrollTop = msgsEl.value.scrollHeight
  })
}

async function send() {
  if (!current.value || !input.value.trim() || streaming.value) return
  const text = input.value.trim()
  input.value = ''
  messages.value.push({
    id: Date.now(),
    session_id: current.value.id,
    role: 'user',
    content: text,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  })
  scrollBottom()

  streaming.value = true
  streamingText.value = ''
  try {
    const url = `${apiBase()}/chat/sessions/${current.value.id}/messages/stream`
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${user.token}`,
      },
      body: JSON.stringify({ content: text }),
    })
    if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let currentEvent = 'message'
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      // SSE 以 \n\n 分帧
      const frames = buf.split('\n\n')
      buf = frames.pop() ?? ''
      for (const frame of frames) {
        currentEvent = 'message'
        let dataLine = ''
        for (const line of frame.split('\n')) {
          if (line.startsWith('event: ')) currentEvent = line.slice(7).trim()
          else if (line.startsWith('data: ')) dataLine = line.slice(6)
        }
        if (!dataLine) continue
        try {
          const parsed = JSON.parse(dataLine)
          if (currentEvent === 'error') {
            ElMessage.error(parsed.error || 'LLM 出错')
            continue
          }
          if (currentEvent === 'done') continue
          if (parsed.delta) {
            streamingText.value += parsed.delta
            scrollBottom()
          }
        } catch {
          // 兼容旧格式：当作原始文本拼接
          streamingText.value += dataLine
          scrollBottom()
        }
      }
    }
    messages.value.push({
      id: Date.now() + 1,
      session_id: current.value.id,
      role: 'assistant',
      content: streamingText.value,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
  } catch (e) {
    ElMessage.error('对话失败：' + (e as Error).message)
  } finally {
    streaming.value = false
    streamingText.value = ''
  }
}

onMounted(loadSessions)
</script>

<style scoped>
.chat-wrap { display: grid; grid-template-columns: 260px 1fr; gap: 16px; height: calc(100vh - 140px); }
.sidebar { overflow: auto; }
.bar { display: flex; justify-content: space-between; align-items: center; }
.sessions { list-style: none; padding: 0; margin: 0; }
.sessions li { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; cursor: pointer; border-radius: 4px; }
.sessions li:hover { background: #f1f5f9; }
.sessions li.active { background: #dbeafe; color: #1d4ed8; }
.sessions .del { opacity: 0.5; }
.sessions .del:hover { color: #dc2626; opacity: 1; }
.conversation { display: flex; flex-direction: column; }
:deep(.conversation .el-card__body) { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.messages { flex: 1; overflow: auto; padding: 8px 0; }
.msg { margin-bottom: 14px; }
.msg .role { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
.msg .bubble { display: inline-block; padding: 10px 14px; border-radius: 10px; max-width: 80%; white-space: pre-wrap; line-height: 1.55; }
.msg.user { text-align: right; }
.msg.user .bubble { background: #dbeafe; color: #1e3a8a; }
.msg.assistant .bubble { background: #f1f5f9; color: #0f172a; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0; } }
.composer { display: flex; gap: 8px; padding-top: 8px; border-top: 1px solid #e2e8f0; }
.composer .el-button { align-self: flex-end; }
</style>
