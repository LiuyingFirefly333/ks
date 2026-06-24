<template>
  <div class="chat-panel qa-workspace">
    <aside class="qa-sidebar">
      <div class="qa-side-actions">
        <button class="full-width" @click="newSession">新建会话</button>
      </div>
      <input
        v-model="sessionQuery"
        class="qa-search"
        placeholder="搜索会话与历史"
        @input="loadSessions"
      />
      <div class="qa-session-list">
        <button
          v-for="s in sessions"
          :key="s.id"
          class="qa-session-item"
          :class="{ active: sessionId === s.id }"
          @click="openSession(s.id)"
        >
          <span>{{ s.title || '未命名会话' }}</span>
          <small>{{ formatDate(s.updated_at || s.created_at) }}</small>
        </button>
      </div>
    </aside>

    <section class="qa-main">
      <div v-if="focusedNode" class="chat-focus-banner">
        <span class="chat-focus-label">当前聚焦：{{ focusedNode.name }}</span>
        <button class="chat-focus-clear" @click="$emit('clear-focus')" title="清除聚焦">×</button>
      </div>

      <div v-if="historyResults.length" class="qa-history-results">
        <div class="section-title">搜索结果 <span>{{ historyResults.length }}</span></div>
        <button
          v-for="row in historyResults"
          :key="row.message.id"
          class="qa-history-item"
          @click="openSession(row.session.id)"
        >
          <strong>{{ row.session.title }}</strong>
          <span>{{ row.message.content }}</span>
        </button>
      </div>

      <div v-if="messages.length === 0 && !historyResults.length" class="chat-empty">
        <div class="chat-empty-icon">AI</div>
        <p>{{ focusedNode ? '围绕「' + focusedNode.name + '」提问' : '基于知识图谱的 AI 问答' }}</p>
        <p class="chat-empty-hint">支持会话保存、历史搜索和回答纠错反馈。</p>
      </div>

      <div class="chat-messages" ref="msgList">
        <div v-for="msg in messages" :key="msg.id || msg.localId" :class="['chat-message', normalizeRole(msg.role)]">
          <div class="chat-bubble">
            <div class="chat-role">{{ normalizeRole(msg.role) === 'user' ? '你' : 'AI 助教' }}</div>
            <div class="chat-text">{{ msg.content }}</div>
            <div v-if="msg.sources && msg.sources.length" class="chat-sources">
              <span class="chat-sources-label">参考知识点</span>
              <span
                v-for="s in msg.sources"
                :key="s.id"
                class="chat-source-tag"
                @click="$emit('locate', s)"
              >
                {{ s.name }}
              </span>
            </div>
            <button
              v-if="normalizeRole(msg.role) === 'ai' && msg.id"
              class="feedback-button"
              @click="openFeedback(msg)"
            >
              纠错反馈
            </button>
          </div>
        </div>

        <div v-if="streaming" class="chat-message ai">
          <div class="chat-bubble">
            <div class="chat-role">AI 助教</div>
            <div class="chat-text">{{ streamingText }}<span class="cursor-blink">|</span></div>
          </div>
        </div>

        <div v-if="loading" class="chat-loading-dots">
          <span class="loading-dot"></span>
          <span class="loading-dot"></span>
          <span class="loading-dot"></span>
        </div>
      </div>

      <div v-if="feedbackTarget" class="feedback-box">
        <div class="section-title">提交纠错</div>
        <textarea v-model="feedbackForm.correction" rows="2" placeholder="说明 AI 回答哪里有问题"></textarea>
        <textarea v-model="feedbackForm.correct_description" rows="2" placeholder="给出正确知识描述，可用于审核后更新图谱"></textarea>
        <div class="feedback-row">
          <select v-model="feedbackForm.target_type">
            <option value="node">更新知识点</option>
            <option value="relation">补充关系</option>
          </select>
          <input v-model="feedbackForm.target_id" placeholder="目标ID，默认取第一个参考知识点" />
        </div>
        <div class="form-actions">
          <button class="secondary" @click="feedbackTarget = null">取消</button>
          <button @click="submitFeedback" :disabled="!feedbackForm.correction.trim()">提交</button>
        </div>
      </div>

      <div class="chat-input-area">
        <input
          v-model="input"
          class="chat-input"
          placeholder="输入问题，按 Enter 发送"
          @keydown.enter="onSend"
          :disabled="streaming || loading"
        />
        <button class="chat-send-btn" @click="onSend" :disabled="streaming || loading || !input.trim()">
          发送
        </button>
        <button v-if="sessionId" class="secondary" @click="deleteCurrentSession">删除</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { qaApi } from '../api/index.js'

const props = defineProps({
  courseId: { type: String, default: '' },
  focusedNode: { type: Object, default: null },
})

defineEmits(['locate', 'clear-focus'])

const sessions = ref([])
const sessionQuery = ref('')
const historyResults = ref([])
const messages = ref([])
const input = ref('')
const loading = ref(false)
const streaming = ref(false)
const streamingText = ref('')
const sessionId = ref(null)
const msgList = ref(null)
const feedbackTarget = ref(null)
const feedbackForm = ref({ correction: '', correct_description: '', target_type: 'node', target_id: '' })
let searchTimer = null

function normalizeRole(role) {
  return role === 'assistant' ? 'ai' : role
}

function formatDate(value) {
  if (!value) return ''
  try { return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) } catch { return '' }
}

async function loadSessions() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    try {
      sessions.value = await qaApi.listSessions(sessionQuery.value.trim() || undefined)
      historyResults.value = sessionQuery.value.trim()
        ? await qaApi.searchHistory(sessionQuery.value.trim())
        : []
    } catch {
      sessions.value = []
      historyResults.value = []
    }
  }, 220)
}

async function newSession() {
  const session = await qaApi.createSession(
    props.focusedNode ? '关于 ' + props.focusedNode.name : '新会话',
    props.courseId || undefined,
    props.focusedNode?.id,
  )
  sessionId.value = session.id
  messages.value = []
  historyResults.value = []
  await loadSessionsNow()
}

async function loadSessionsNow() {
  sessions.value = await qaApi.listSessions(sessionQuery.value.trim() || undefined)
}

async function openSession(id) {
  const data = await qaApi.getSession(id)
  sessionId.value = data.session.id
  messages.value = (data.messages || []).map(m => ({ ...m, role: normalizeRole(m.role) }))
  historyResults.value = []
  await nextTick()
  scrollToBottom()
}

async function deleteCurrentSession() {
  if (!sessionId.value || !confirm('确认删除当前 AI 会话？')) return
  await qaApi.deleteSession(sessionId.value)
  sessionId.value = null
  messages.value = []
  await loadSessionsNow()
}

async function onSend() {
  const text = input.value.trim()
  if (!text || streaming.value || loading.value) return

  if (!sessionId.value) {
    await newSession()
  }

  input.value = ''
  messages.value.push({ localId: Date.now() + '-u', role: 'user', content: text, sources: [] })
  loading.value = true
  await nextTick()
  scrollToBottom()

  const nodeId = props.focusedNode?.id

  try {
    streaming.value = true
    loading.value = false
    streamingText.value = ''
    let pendingSources = []
    let pendingMessageId = ''

    await qaApi.askStream(
      text,
      props.courseId || undefined,
      nodeId,
      sessionId.value,
      (token) => {
        streamingText.value += token
        scrollToBottom()
      },
      (sources, sid) => {
        pendingSources = sources || []
        if (sid) sessionId.value = sid
      },
      (messageId) => {
        pendingMessageId = messageId || ''
        messages.value.push({
          id: pendingMessageId,
          role: 'ai',
          content: streamingText.value,
          sources: pendingSources,
        })
        streamingText.value = ''
        streaming.value = false
        loadSessionsNow()
        scrollToBottom()
      },
      (err) => {
        messages.value.push({
          localId: Date.now() + '-e',
          role: 'ai',
          content: '抱歉，AI 服务暂时不可用：' + err,
          sources: [],
        })
        streamingText.value = ''
        streaming.value = false
      }
    )
  } catch (e) {
    streaming.value = false
    messages.value.push({
      localId: Date.now() + '-err',
      role: 'ai',
      content: '请求失败：' + (e.normalizedMessage || e.message || e),
      sources: [],
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function openFeedback(msg) {
  const firstSource = msg.sources?.[0]
  feedbackTarget.value = msg
  feedbackForm.value = {
    correction: '',
    correct_description: '',
    target_type: 'node',
    target_id: firstSource?.id || '',
  }
}

async function submitFeedback() {
  if (!feedbackTarget.value || !sessionId.value) return
  await qaApi.submitFeedback({
    session_id: sessionId.value,
    message_id: feedbackTarget.value.id,
    correction: feedbackForm.value.correction,
    correct_description: feedbackForm.value.correct_description,
    target_type: feedbackForm.value.target_type,
    target_id: feedbackForm.value.target_id,
  })
  feedbackTarget.value = null
  feedbackForm.value = { correction: '', correct_description: '', target_type: 'node', target_id: '' }
}

function scrollToBottom() {
  if (msgList.value) {
    const el = msgList.value
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight
    })
  }
}

watch(() => props.focusedNode?.id, () => {
  if (!sessionId.value) return
  feedbackTarget.value = null
})

onMounted(async () => {
  await loadSessionsNow()
})
</script>
