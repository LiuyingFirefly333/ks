<template>
  <div class="discuss-panel">
    <h4>讨论区 ({{ comments.length }})</h4>

    <!-- 评论列表 -->
    <div v-if="comments.length === 0" class="empty-state" style="padding:8px;font-size:12px">暂无讨论</div>
    <div v-for="c in comments" :key="c.id" class="discuss-item">
      <div class="discuss-header">
        <span class="discuss-user">{{ c.user_name }}</span>
        <span class="discuss-time">{{ fmtDate(c.created_at) }}</span>
        <button v-if="c.user_id === userId" class="discuss-del" @click="onDelete(c.id)">&times;</button>
      </div>
      <div class="discuss-content">{{ c.content }}</div>
    </div>

    <!-- 输入区 -->
    <div class="discuss-input-area">
      <textarea v-model="newComment" rows="2" placeholder="发表你的疑问或讨论..."
        @keydown.enter.ctrl="onAdd"></textarea>
      <button @click="onAdd" :disabled="!newComment.trim() || loading">发 布</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { discussApi } from '../api/index.js'

const props = defineProps({
  nodeId: { type: String, default: '' },
  userId: { type: String, default: '' },
  userRole: { type: String, default: 'student' },
})

const comments = ref([])
const newComment = ref('')
const loading = ref(false)

watch(() => props.nodeId, async (val) => {
  if (val) {
    try { comments.value = await discussApi.listComments(val) } catch { comments.value = [] }
  } else { comments.value = [] }
}, { immediate: true })

async function onAdd() {
  if (!newComment.value.trim() || !props.nodeId || !props.userId) return
  loading.value = true
  try {
    const c = await discussApi.addComment(props.userId, props.nodeId, newComment.value.trim(), props.userRole)
    comments.value.unshift({ ...c, user_name: '我' })
    newComment.value = ''
  } catch {}
  loading.value = false
}

async function onDelete(id) {
  try { await discussApi.deleteComment(id); comments.value = comments.value.filter(c => c.id !== id) } catch {}
}

function fmtDate(d) { try { return new Date(d).toLocaleDateString('zh-CN') } catch { return d } }
</script>