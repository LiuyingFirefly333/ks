<template>
  <div class="chat-panel">
    <!-- 节点聚焦提示 -->
    <div v-if="focusedNode" class="chat-focus-banner">
      <span class="chat-focus-label">当前聚焦：{{ focusedNode.name }}</span>
      <button class="chat-focus-clear" @click="$emit('clear-focus')">&times;</button>
    </div>

    <!-- 空状态 -->
    <div v-if="messages.length === 0" class="chat-empty">
      <div class="chat-empty-icon">?</div>
      <p>{{ focusedNode ? '针对「' + focusedNode.name + '」提问' : '基于知识图谱的 AI 问答' }}</p>
      <p class="chat-empty-hint">支持多轮对话，试试追问: 能举个例子吗？</p>
    </div>

    <!-- 消息列表 -->
    <div class="chat-messages" ref="msgList">
      <div v-for="(msg, i) in messages" :key="i" :class="['chat-message', msg.role]">
        <div class="chat-bubble">
          <div class="chat-role">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
          <div class="chat-text">{{ msg.content }}</div>
          <div v-if="msg.sources && msg.sources.length" class="chat-sources">
            <span class="chat-sources-label">参考：</span>
            <span v-for="s in msg.sources" :key="s.id" class="chat-source-tag"
              @click="$emit('locate', s)">{{ s.name }}</span>
          </div>
        </div>
      </div>

      <!-- 流式输出气泡 -->
      <div v-if="streaming" class="chat-message ai">
        <div class="chat-bubble">
          <div class="chat-role">AI</div>
          <div class="chat-text">{{ streamingText }}<span class="cursor-blink">|</span></div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="chat-loading-dots">
        <span class="loading-dot"></span>
        <span class="loading-dot"></span>
        <span class="loading-dot"></span>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="chat-input-area">
      <input v-model="input" class="chat-input" placeholder="输入问题，Enter 发送..."
        @keydown.enter="onSend" :disabled="streaming || loading" />
      <button class="chat-send-btn" @click="onSend"
        :disabled="streaming || loading || !input.trim()">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onUnmounted } from 'vue'
import { qaApi } from '../api/index.js'

const props = defineProps({
  courseId: { type: String, default: '' },
  focusedNode: { type: Object, default: null },
})

const emit = defineEmits(['locate', 'clear-focus'])

const messages = ref([])
const input = ref('')
const loading = ref(false)
const streaming = ref(false)
const streamingText = ref('')
const sessionId = ref(null)
const msgList = ref(null)
let abortController = null

async function onSend() {
  const text = input.value.trim()
  if (!text || streaming.value || loading.value) return

  input.value = ''
  messages.value.push({ role: 'user', content: text })
  loading.value = true
  await nextTick()
  scrollToBottom()

  const nodeId = props.focusedNode?.id

  try {
    // 使用流式 API
    streaming.value = true
    loading.value = false
    streamingText.value = ''
    let pendingSources = null

    await qaApi.askStream(
      text, props.courseId || undefined, nodeId, sessionId.value,
      // onToken
      (token) => {
        streamingText.value += token
        scrollToBottom()
      },
      // onSources
      (sources, sid) => {
        pendingSources = sources
        if (sid) sessionId.value = sid
      },
      // onDone
      () => {
        messages.value.push({
          role: 'ai',
          content: streamingText.value,
          sources: pendingSources || [],
        })
        streamingText.value = ''
        pendingSources = null
        streaming.value = false
        scrollToBottom()
      },
      // onError
      (err) => {
        if (streamingText.value) {
          messages.value.push({
            role: 'ai',
            content: streamingText.value + '\n\n[连接中断: ' + err + ']',
            sources: pendingSources || [],
          })
          streamingText.value = ''
        } else {
          messages.value.push({
            role: 'ai',
            content: '抱歉，AI 服务暂时不可用：' + err,
            sources: [],
          })
        }
        pendingSources = null
        streaming.value = false
      }
    )
  } catch (e) {
    streaming.value = false
    messages.value.push({
      role: 'ai',
      content: '请求失败: ' + (e.message || e),
      sources: [],
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  if (msgList.value) {
    const el = msgList.value
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight
    })
  }
}

onUnmounted(() => {
  if (abortController) abortController.abort()
})
</script>