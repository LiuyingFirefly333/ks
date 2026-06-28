<template>
  <div class="path-panel">
    <div v-if="!hasAnyPath && !loading && !error" class="empty-state">
      选择一个目标知识点，系统会结合综合掌握度、前置依赖和资源自动生成学习任务。
    </div>

    <div v-if="loading" class="loading-spinner"></div>
    <div v-if="error" class="inline-error">{{ error }}</div>
    <div v-if="compareNotice && hasAnyPath" class="inline-hint">{{ compareNotice }}</div>

    <div v-if="hasAnyPath">
      <div class="path-type-tabs">
        <button
          v-for="type in pathTypes"
          :key="type.key"
          :class="{ active: currentType === type.key, unavailable: !pathResults[type.key]?.path?.length }"
          :style="{ '--tab-color': type.color }"
          :disabled="!pathResults[type.key]?.path?.length"
          @click="switchPath(type.key)"
        >
          {{ type.label }}
        </button>
      </div>

      <div class="path-compare-summary">
        <button
          v-for="item in availablePathSummaries"
          :key="item.key"
          class="path-summary-item"
          :class="{ active: currentType === item.key }"
          @click="switchPath(item.key)"
        >
          <span class="path-color-dot" :style="{ background: item.color }"></span>
          <b>{{ item.label }}</b>
          <small>{{ item.count }} 点 · {{ item.totalTime }} 分钟</small>
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

      <div class="learning-explain-card">
        <div>
          <span class="explain-label">推荐原因</span>
          <p>{{ recommendationReason }}</p>
        </div>
        <div>
          <span class="explain-label">下一步动作</span>
          <button
            class="inline-action"
            :disabled="!nextActionNode"
            @click="locateNextAction"
          >
            {{ nextActionLabel }}
          </button>
        </div>
      </div>

      <div v-if="pathBasisText || pathScores.length" class="path-evidence-panel">
        <div v-if="pathBasisText">
          <span class="explain-label">推荐依据</span>
          <p>{{ pathBasisText }}</p>
        </div>
        <div v-if="pathScores.length" class="path-score-row">
          <span v-for="item in pathScores" :key="item.key" class="path-score-chip">
            {{ item.label }} {{ item.value }}
          </span>
        </div>
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
import { computed, ref } from 'vue'
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

const pathResults = ref({})
const loading = ref(false)
const error = ref('')
const compareNotice = ref('')
const currentType = ref('shortest')
const currentPath = computed(() => pathResults.value[currentType.value] || emptyPathPayload(currentType.value))
const pathResult = computed(() => currentPath.value.path || [])
const tasks = computed(() => currentPath.value.tasks || [])
const weakPrerequisites = computed(() => currentPath.value.weak_prerequisites || [])
const totalTime = computed(() => currentPath.value.total_estimated_time || 0)
const completedCount = computed(() => currentPath.value.completed_count || 0)
const progress = computed(() => currentPath.value.progress || 0)
const recommendationReason = computed(() => {
  if (currentPath.value.reason) return currentPath.value.reason
  if (weakPrerequisites.value.length) return `检测到 ${weakPrerequisites.value.length} 个薄弱前置知识，因此优先展示完整补齐路径。`
  return `${currentTypeLabel.value}会结合掌握度、前置关系和预计学习时间生成任务顺序。`
})
const pathBasisText = computed(() => {
  const basis = currentPath.value.basis || {}
  const weakCount = basis.weak_prerequisites?.length || 0
  const masteryCount = (basis.mastery || []).filter(item => item.score > 0).length
  const edgeCount = basis.prerequisite_edges?.length || 0
  const parts = []
  if (masteryCount) parts.push(`${masteryCount} 个已有掌握度记录`)
  if (weakCount) parts.push(`${weakCount} 个薄弱前置知识`)
  if (edgeCount) parts.push(`${edgeCount} 条前置关系`)
  return parts.length ? `本路径依据 ${parts.join('、')} 生成。` : ''
})
const pathScores = computed(() => {
  const scores = currentPath.value.scores || {}
  return [
    { key: 'time', label: '时间', value: scores.time },
    { key: 'difficulty', label: '难度', value: scores.difficulty },
    { key: 'coverage', label: '覆盖', value: scores.coverage },
  ].filter(item => Number.isFinite(Number(item.value)))
})
const nextActionLabel = computed(() => currentPath.value.next_action?.label || fallbackNextAction()?.label || '继续完成路径任务')
const nextActionNode = computed(() => {
  const action = currentPath.value.next_action
  if (action?.node_id) return { id: action.node_id, name: action.node_name }
  const task = fallbackNextAction()?.task
  return task ? taskToNode(task) : null
})
const currentTypeMeta = computed(() => pathTypes.find(item => item.key === currentType.value) || pathTypes[0])
const currentTypeColor = computed(() => currentTypeMeta.value.color)
const currentTypeLabel = computed(() => currentTypeMeta.value.label)
const hasAnyPath = computed(() => pathTypes.some(type => pathResults.value[type.key]?.path?.length))
const availablePathSummaries = computed(() => pathTypes
  .map(type => {
    const result = pathResults.value[type.key]
    if (!result?.path?.length) return null
    return {
      key: type.key,
      label: type.label,
      color: type.color,
      count: result.path.length,
      totalTime: result.total_estimated_time || 0,
    }
  })
  .filter(Boolean))

function switchPath(type) {
  if (!pathResults.value[type]?.path?.length) return
  currentType.value = type
}

function fallbackNextAction() {
  const task = tasks.value.find(item => item.status !== 'completed')
  if (!task) return { label: '当前路径已完成，进入专项训练巩固', task: null }
  return { label: `先处理：${task.name}`, task }
}

function locateNextAction() {
  if (nextActionNode.value) emit('locate', nextActionNode.value)
}

async function fetchPath(targetId) {
  loading.value = true
  error.value = ''
  compareNotice.value = ''
  pathResults.value = {}

  try {
    const settled = await Promise.allSettled(pathTypes.map(type => fetchPathByType(type.key, targetId)))
    const nextResults = {}
    let failedCount = 0

    settled.forEach((item, index) => {
      const type = pathTypes[index]
      if (item.status === 'fulfilled' && item.value?.path?.length) {
        nextResults[type.key] = normalizePathPayload(item.value, type.key)
      } else {
        failedCount += 1
      }
    })

    if (!Object.keys(nextResults).length) {
      const roadmap = await recommendApi.getRoadmap(targetId, props.studentId)
      if (roadmap.path && roadmap.path.length) {
        nextResults.shortest = normalizePathPayload(roadmap, 'shortest')
      } else {
        error.value = '未找到可行路径'
      }
    }

    pathResults.value = nextResults
    if (!pathResults.value[currentType.value]?.path?.length) {
      currentType.value = availablePathSummaries.value[0]?.key || 'shortest'
    }
    if (failedCount && hasAnyPath.value) compareNotice.value = '部分路径暂不可用，已展示可生成的推荐结果。'
    emitPathResults()
  } catch (err) {
    error.value = err.normalizedMessage || '路径推荐失败，请检查后端连接'
  } finally {
    loading.value = false
  }
}

function fallbackMastered() {
  return props.masteredIds.length ? props.masteredIds : ['n1', 'n2']
}

async function fetchPathByType(type, targetId) {
  if (type === 'easy') {
    return props.studentId
      ? recommendApi.recommendEasyPath(props.studentId, targetId)
      : apiPost('/recommend/path/easy', { mastered: fallbackMastered(), target: targetId })
  }
  if (type === 'thorough') {
    return props.studentId
      ? recommendApi.recommendThoroughPath(props.studentId, targetId)
      : apiPost('/recommend/path/thorough', { mastered: fallbackMastered(), target: targetId })
  }
  return props.studentId
    ? recommendApi.recommendPathForStudent(props.studentId, targetId)
    : recommendApi.recommendPath(fallbackMastered(), targetId)
}

function emptyPathPayload(type) {
  return {
    type,
    path: [],
    tasks: [],
    weak_prerequisites: [],
    total_estimated_time: 0,
    completed_count: 0,
    progress: 0,
  }
}

function normalizePathPayload(data, type) {
  const path = data.path || []
  const normalizedTasks = data.tasks || path.map((node, index) => ({
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
  return {
    ...data,
    type,
    path,
    tasks: normalizedTasks,
    weak_prerequisites: data.weak_prerequisites || [],
    total_estimated_time: data.total_estimated_time || 0,
    completed_count: data.completed_count || 0,
    progress: data.progress || 0,
    reason: data.reason || '',
    next_action: data.next_action || null,
    basis: data.basis || {},
    scores: data.scores || {},
  }
}

function emitPathResults() {
  const highlightedPaths = pathTypes
    .map(type => {
      const result = pathResults.value[type.key]
      if (!result?.path?.length) return null
      return {
        type: type.key,
        label: type.label,
        color: type.color,
        path: result.path,
        total_estimated_time: result.total_estimated_time || 0,
      }
    })
    .filter(Boolean)
  emit('path-found', pathResult.value, totalTime.value, currentType.value, highlightedPaths)
}

async function apiPost(url, body) {
  const response = await api.post(url, body)
  return response.data
}

function doClear() {
  pathResults.value = {}
  error.value = ''
  compareNotice.value = ''
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
