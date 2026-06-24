<template>
  <div class="path-panel">
    <div v-if="!tasks.length && !loading && !error" class="empty-state">
      选择一个目标知识点，系统会结合综合掌握度、前置依赖和资源自动生成学习任务。
    </div>

    <div v-if="loading" class="loading-spinner"></div>
    <div v-if="error" class="inline-error">{{ error }}</div>

    <div v-if="tasks.length">
      <div class="path-type-tabs">
        <button
          v-for="type in pathTypes"
          :key="type.key"
          :class="{ active: currentType === type.key }"
          :style="{ '--tab-color': type.color }"
          @click="switchPath(type.key)"
        >
          {{ type.label }}
        </button>
      </div>

      <div class="path-info">
        <span class="path-type-badge" :style="{ background: currentTypeColor }">{{ currentTypeLabel }}</span>
        <span>{{ tasks.length }} 个任务</span>
        <span v-if="totalTime > 0">预计 {{ totalTime }} 分钟</span>
        <span>已完成 {{ completedCount }} / {{ tasks.length }}</span>
        <span>进度 {{ Math.round(progress * 100) }}%</span>
      </div>

      <div v-if="weakPrerequisites.length" class="path-blocker">
        <strong>存在薄弱前置知识，建议优先补齐：</strong>
        <span
          v-for="node in weakPrerequisites"
          :key="node.id"
          class="weak-node-tag"
          @click="$emit('locate', node)"
        >
          {{ node.name }} · {{ levelLabel(node.mastery_level) }}
        </span>
      </div>

      <div class="path-timeline">
        <div
          v-for="task in tasks"
          :key="task.node_id"
          class="path-step-group"
          :class="'status-' + task.status"
        >
          <div class="path-step" @click="$emit('locate', taskToNode(task))">
            <span class="index" :style="{ background: statusColor(task) }">{{ task.index }}</span>
            <div class="path-step-main">
              <span class="path-step-name">{{ task.name }}</span>
              <span class="path-step-meta">
                {{ task.category || '未分类' }} · {{ levelLabel(task.mastery_level) }} · {{ task.mastery_score }} 分
              </span>
            </div>
            <span class="task-status">{{ statusLabel(task.status) }}</span>
          </div>

          <div class="path-resources">
            <span v-if="task.estimated_time" class="path-res-tag time">{{ task.estimated_time }} 分钟</span>
            <a
              v-for="(resource, index) in linkResources(task.resources)"
              :key="index"
              class="path-res-tag link"
              :href="resource.url"
              target="_blank"
              rel="noreferrer"
            >
              {{ resource.title }}
            </a>
            <button
              v-for="(resource, index) in aiResources(task.resources)"
              :key="'ai' + index"
              class="path-res-tag button-tag"
              @click="$emit('locate', taskToNode(task))"
            >
              {{ resource.title }}
            </button>
          </div>
        </div>
      </div>

      <button class="secondary full-width" @click="doClear">清除路径</button>
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
  { key: 'easy', label: '最轻松', color: '#16a34a' },
  { key: 'thorough', label: '最扎实', color: '#2563eb' },
]

const pathResult = ref([])
const tasks = ref([])
const weakPrerequisites = ref([])
const totalTime = ref(0)
const completedCount = ref(0)
const progress = ref(0)
const loading = ref(false)
const error = ref('')
const currentType = ref('shortest')
const currentTypeColor = ref('#ef4444')
const currentTypeLabel = ref('最短路径')

function switchPath(type) {
  currentType.value = type
  const selectedType = pathTypes.find(item => item.key === type)
  currentTypeColor.value = selectedType?.color || '#ef4444'
  currentTypeLabel.value = selectedType?.label || '最短路径'
  if (props.targetNode) fetchPath(props.targetNode.id)
}

async function fetchPath(targetId) {
  loading.value = true
  error.value = ''
  pathResult.value = []
  tasks.value = []
  weakPrerequisites.value = []
  totalTime.value = 0
  completedCount.value = 0
  progress.value = 0

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
      const roadmap = await recommendApi.getRoadmap(targetId, props.studentId)
      if (roadmap.path && roadmap.path.length) applyPath(roadmap)
      else error.value = '未找到可行路径'
    }
  } catch (err) {
    error.value = err.normalizedMessage || '路径推荐失败，请检查后端连接'
  } finally {
    loading.value = false
  }
}

function fallbackMastered() {
  return props.masteredIds.length ? props.masteredIds : ['n1', 'n2']
}

function applyPath(data) {
  pathResult.value = data.path || []
  tasks.value = data.tasks || pathResult.value.map((node, index) => ({
    index: index + 1,
    node_id: node.id,
    name: node.name,
    category: node.category,
    difficulty: node.difficulty,
    estimated_time: node.estimated_time || 0,
    mastery_score: node.mastery_score || 0,
    mastery_level: node.mastery_level || 'unlearned',
    status: 'pending',
    resources: [],
  }))
  weakPrerequisites.value = data.weak_prerequisites || []
  totalTime.value = data.total_estimated_time || 0
  completedCount.value = data.completed_count || 0
  progress.value = data.progress || 0
  emit('path-found', pathResult.value, totalTime.value, currentType.value)
}

async function apiPost(url, body) {
  const response = await api.post(url, body)
  return response.data
}

function doClear() {
  pathResult.value = []
  tasks.value = []
  weakPrerequisites.value = []
  error.value = ''
  totalTime.value = 0
  completedCount.value = 0
  progress.value = 0
  emit('clear')
}

function taskToNode(task) {
  return {
    id: task.node_id,
    name: task.name,
    category: task.category,
    difficulty: task.difficulty,
    estimated_time: task.estimated_time,
  }
}

function levelLabel(level) {
  return {
    proficient: '熟练',
    fair: '一般',
    weak: '薄弱',
    unlearned: '未学习',
  }[level] || '未学习'
}

function statusLabel(status) {
  return {
    completed: '已完成',
    review: '需复习',
    pending: '待学习',
  }[status] || '待学习'
}

function statusColor(task) {
  return {
    completed: '#16a34a',
    review: '#f59e0b',
    pending: '#2563eb',
  }[task.status] || currentTypeColor.value
}

function linkResources(resources = []) {
  return resources.filter(resource => resource.url)
}

function aiResources(resources = []) {
  return resources.filter(resource => resource.type === 'ai')
}

defineExpose({ fetchPath, clear: doClear })
</script>
