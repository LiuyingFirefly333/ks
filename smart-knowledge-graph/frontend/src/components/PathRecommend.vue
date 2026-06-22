<template>
  <div>
    <div v-if="!pathResult.length && !loading && !error" class="empty-state">
      选择一个目标知识点，系统将推荐学习路径
    </div>

    <div v-if="loading" class="loading-spinner"></div>
    <div v-if="error" style="color: var(--accent-red); font-size: 13px; padding: 8px 0">{{ error }}</div>

    <div v-if="pathResult.length">
      <div class="path-type-tabs">
        <button
          v-for="t in pathTypes"
          :key="t.key"
          :class="{ active: currentType === t.key }"
          :style="{ borderColor: currentType === t.key ? t.color : 'transparent' }"
          @click="switchPath(t.key)"
        >
          {{ t.label }}
        </button>
      </div>

      <div class="path-info">
        推荐学习路径（{{ pathResult.length }} 步<span v-if="totalTime > 0">，预计 {{ totalTime }} 分钟</span>）
        <span class="path-type-badge" :style="{ background: currentTypeColor }">{{ currentTypeLabel }}</span>
      </div>

      <div v-for="(step, idx) in pathResult" :key="step.id" class="path-step-group">
        <div class="path-step" @click="$emit('locate', step)" style="cursor:pointer">
          <span class="index" :style="{ background: currentTypeColor }">{{ idx + 1 }}</span>
          <span>{{ step.name }}</span>
          <span v-if="idx < pathResult.length - 1" class="arrow">&rarr;</span>
        </div>
        <div v-if="step.video_urls?.length || step.exercises?.length || step.estimated_time" class="path-resources">
          <span v-if="step.video_urls?.length" class="path-res-tag" title="有视频资源">视频 {{ step.video_urls.length }}</span>
          <span v-if="step.exercises?.length" class="path-res-tag" title="有习题资源">习题 {{ step.exercises.length }}</span>
          <span v-if="step.estimated_time" class="path-res-tag time" title="预计时长">{{ step.estimated_time }} 分钟</span>
        </div>
      </div>

      <button style="margin-top:10px; width:100%" class="ghost" @click="doClear">清除路径</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api, { recommendApi } from '../api/index.js'

const emit = defineEmits(['locate', 'clear', 'path-found'])
const props = defineProps({
  targetNode: { type: Object, default: null },
  masteredIds: { type: Array, default: () => [] },
  studentId: { type: String, default: null },
})

const pathTypes = [
  { key: 'shortest', label: '最短路径', color: '#ef4444' },
  { key: 'easy', label: '最轻松', color: '#22c55e' },
  { key: 'thorough', label: '最扎实', color: '#3b82f6' },
]

const pathResult = ref([])
const totalTime = ref(0)
const loading = ref(false)
const error = ref('')
const currentType = ref('shortest')
const currentTypeColor = ref('#ef4444')
const currentTypeLabel = ref('最短路径')

function switchPath(type) {
  currentType.value = type
  const t = pathTypes.find(p => p.key === type)
  currentTypeColor.value = t?.color || '#ef4444'
  currentTypeLabel.value = t?.label || '最短路径'
  if (props.targetNode) fetchPath(props.targetNode.id)
}

async function fetchPath(targetId) {
  loading.value = true
  error.value = ''
  pathResult.value = []
  totalTime.value = 0
  try {
    let data
    if (currentType.value === 'easy') {
      data = props.studentId
        ? await recommendApi.recommendEasyPath(props.studentId, targetId)
        : await apiPost('/recommend/path/easy', { mastered: fallbackMastered(), target: targetId })
    } else if (currentType.value === 'thorough') {
      data = props.studentId
        ? await recommendApi.recommendThoroughPath(props.studentId, targetId)
        : await apiPost('/recommend/path/thorough', { mastered: fallbackMastered(), target: targetId })
    } else {
      data = props.studentId
        ? await recommendApi.recommendPathForStudent(props.studentId, targetId)
        : await recommendApi.recommendPath(fallbackMastered(), targetId)
    }

    if (data.path && data.path.length) {
      applyPath(data)
    } else {
      const roadmap = await recommendApi.getRoadmap(targetId)
      if (roadmap.path && roadmap.path.length) applyPath(roadmap)
      else error.value = '未找到可行路径'
    }
  } catch {
    error.value = '路径推荐失败，请检查后端连接'
  } finally {
    loading.value = false
  }
}

function fallbackMastered() {
  return props.masteredIds.length ? props.masteredIds : ['n1', 'n2']
}

function applyPath(data) {
  pathResult.value = data.path
  totalTime.value = data.total_estimated_time || 0
  emit('path-found', data.path, totalTime.value, currentType.value)
}

async function apiPost(url, body) {
  const r = await api.post(url, body)
  return r.data
}

function doClear() {
  pathResult.value = []
  error.value = ''
  totalTime.value = 0
  emit('clear')
}

defineExpose({ fetchPath, clear: doClear })
</script>
