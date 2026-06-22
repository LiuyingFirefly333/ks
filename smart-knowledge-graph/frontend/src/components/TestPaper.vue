<template>
  <div class="test-paper">
    <div class="test-paper-actions">
      <button @click="generate" :disabled="loading || !studentId">生成组卷</button>
      <span v-if="generated" class="test-meta">
        {{ exercises.length }} 题 | 知识点 {{ weakNodes.length }} 个
      </span>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-if="!loading && !generated" class="empty-state">
      基于你的薄弱知识点和错题记录，自动生成专项训练卷
    </div>

    <div v-if="generated && weakNodes.length" class="test-weak-nodes">
      <div class="test-label">薄弱知识点：</div>
      <span v-for="n in weakNodes" :key="n.id" class="weak-node-tag"
        @click="$emit('locate-node', n.id)">
        {{ n.name }}
      </span>
    </div>

    <div v-if="generated && exercises.length" class="test-exercises">
      <div class="test-label">专项练习题 ({{ exercises.length }} 题)：</div>
      <div v-for="(ex, idx) in exercises" :key="idx" class="test-exercise-card">
        <div class="test-ex-num">{{ idx + 1 }}</div>
        <div class="test-ex-info">
          <div class="test-ex-node" @click="$emit('locate-node', ex.node_id)">
            {{ ex.node_name }}
          </div>
          <a :href="ex.url" target="_blank" class="test-ex-link">打开习题</a>
        </div>
      </div>
    </div>

    <div v-if="generated && !exercises.length" class="empty-state">
      当前薄弱知识点暂无绑定习题资源
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { examApi } from '../api/index.js'

const props = defineProps({
  studentId: { type: String, default: '' },
  courseId: { type: String, default: '' },
})
const emit = defineEmits(['locate-node'])

const loading = ref(false)
const generated = ref(false)
const weakNodes = ref([])
const exercises = ref([])

async function generate() {
  if (!props.studentId) return
  loading.value = true
  try {
    const data = await examApi.generateTest(props.studentId, props.courseId, 15)
    weakNodes.value = data.weak_nodes || []
    exercises.value = data.exercises || []
    generated.value = true
  } catch { generated.value = false }
  loading.value = false
}
</script>