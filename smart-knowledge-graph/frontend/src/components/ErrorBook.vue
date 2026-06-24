<template>
  <div class="error-book">
    <div class="panel-actions">
      <button class="secondary" @click="fetchErrors" :disabled="loading">刷新错题</button>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-if="!loading && errors.length === 0" class="empty-state">
      暂无错题记录。完成练习后，错题会在这里自动沉淀。
    </div>

    <div v-for="err in errors" :key="err.id" class="error-card">
      <div class="error-card-header">
        <span class="error-node-badge" @click="$emit('locate-node', err.node_id)">
          {{ err.node_name }}
        </span>
        <span class="error-date">{{ fmtDate(err.created_at) }}</span>
        <button class="icon-button subtle" @click="onDelete(err.id)" title="删除">×</button>
      </div>
      <div class="error-question">{{ err.question }}</div>
      <div class="error-answers">
        <div class="error-ans wrong">你的答案：{{ err.student_answer }}</div>
        <div class="error-ans correct">正确答案：{{ err.correct_answer }}</div>
      </div>
      <div v-if="err.error_reason" class="error-reason">{{ err.error_reason }}</div>
      <button class="error-trace-btn" @click="onTrace(err)">
        {{ traceErrorId === err.id ? '收起溯源' : '知识点溯源' }}
      </button>

      <div v-if="traceErrorId === err.id" class="error-trace">
        <div v-if="traceLoading" class="loading-spinner"></div>
        <div v-else-if="traceData">
          <div class="trace-node">
            <strong>错题考点：{{ traceData.node.name }}</strong>
            <p>{{ traceData.node.description || '暂无考点说明' }}</p>
          </div>
          <div v-if="traceData.prerequisites.length" class="trace-prereqs">
            <div class="trace-label">前置知识链 {{ traceData.prerequisites.length }} 个</div>
            <div v-for="p in traceData.prerequisites" :key="p.id" class="trace-item"
              @click="$emit('locate-node', p.id)">
              {{ p.name }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { examApi } from '../api/index.js'

const props = defineProps({
  studentId: { type: String, default: '' },
})
const emit = defineEmits(['locate-node'])

const errors = ref([])
const loading = ref(false)
const traceErrorId = ref(null)
const traceData = ref(null)
const traceLoading = ref(false)

async function fetchErrors() {
  if (!props.studentId) return
  loading.value = true
  try { errors.value = await examApi.listErrors(props.studentId) } catch { errors.value = [] }
  loading.value = false
}

async function onDelete(id) {
  try { await examApi.deleteError(id); errors.value = errors.value.filter(e => e.id !== id) } catch {}
}

async function onTrace(err) {
  if (traceErrorId.value === err.id) { traceErrorId.value = null; return }
  traceErrorId.value = err.id
  traceLoading.value = true
  try { traceData.value = await examApi.errorTrace(err.id) } catch { traceData.value = null }
  traceLoading.value = false
}

function fmtDate(d) {
  if (!d) return ''
  try { return new Date(d).toLocaleDateString('zh-CN') } catch { return d }
}

onMounted(() => fetchErrors())
</script>
