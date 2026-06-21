<template>
  <div>
    <div v-if="!pathResult.length && !loading && !error" class="empty-state">
      选择一个目标知识点，系统将推荐最优学习路径
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-if="error" style="color: var(--accent-red); font-size: 13px; padding: 8px 0">
      {{ error }}
    </div>

    <div v-if="pathResult.length" class="path-result">
      <div style="margin-bottom: 8px; font-size: 12px; color: var(--text-muted)">
        推荐学习路径（{{ pathResult.length }} 步）
      </div>
      <div
        v-for="(step, idx) in pathResult"
        :key="step.id"
        class="path-step"
        @click="$emit('locate', step)"
        style="cursor:pointer"
      >
        <span class="index">{{ idx + 1 }}</span>
        <span>{{ step.name }}</span>
        <span v-if="idx < pathResult.length - 1" class="arrow">&rarr;</span>
      </div>
      <button style="margin-top:10px; width:100%" class="ghost" @click="doClear">清除路径</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { recommendApi } from '../api/index.js'

const emit = defineEmits(['locate', 'clear', 'path-found'])
const props = defineProps({
  targetNode: { type: Object, default: null },
  masteredIds: { type: Array, default: () => [] },
  studentId: { type: String, default: null },
})

const pathResult = ref([])
const totalTime = ref(0)
const loading = ref(false)
const error = ref('')

async function fetchPath(targetId) {
  loading.value = true
  error.value = ''
  pathResult.value = []
  try {
    let data
    if (props.studentId) {
      data = await recommendApi.recommendPathForStudent(props.studentId, targetId)
    } else {
      let mastered = props.masteredIds
      if (!mastered.length) {
        mastered = ['n1', 'n2']
      }
      data = await recommendApi.recommendPath(mastered, targetId)
    }
    if (data.path && data.path.length) {
      pathResult.value = data.path
      totalTime.value = data.total_estimated_time || 0; emit('path-found', data.path, totalTime.value)
    } else {
      const roadmap = await recommendApi.getRoadmap(targetId)
      if (roadmap.path && roadmap.path.length) {
        pathResult.value = roadmap.path
        emit('path-found', roadmap.path)
      } else {
        error.value = '未找到可行路径'
      }
    }
  } catch (e) {
    error.value = '路径推荐失败，请检查后端连接'
  } finally {
    loading.value = false
  }
}

function doClear() {
  pathResult.value = []
  error.value = ''
  emit('clear')
}

defineExpose({ fetchPath, clear: doClear })
</script>
