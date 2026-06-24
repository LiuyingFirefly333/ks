<template>
  <div class="admin-dashboard">
    <div class="admin-stats">
      <div class="stat-card"><div class="stat-num">{{ stats.total_nodes }}</div><div class="stat-label">知识点</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_students }}</div><div class="stat-label">学生</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_teachers }}</div><div class="stat-label">教师</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_classes }}</div><div class="stat-label">班级</div></div>
    </div>
    <button class="secondary" @click="refreshAll">刷新数据</button>

    <div v-if="stats.hot_nodes?.length" class="admin-section">
      <h4>热点知识点 TOP 10</h4>
      <div v-for="h in stats.hot_nodes" :key="h.node_id" class="admin-hot-row">
        <span class="admin-hot-name" @click="$emit('locate', h.node_id)">{{ h.name }}</span>
        <span class="admin-hot-meta">{{ h.assess_count }} 次 · 均分 {{ h.avg_score }}</span>
      </div>
    </div>

    <div class="admin-section">
      <div class="section-head">
        <h4>AI 纠错审核</h4>
        <button class="secondary small" @click="fetchFeedback">刷新</button>
      </div>
      <div v-if="feedback.length === 0" class="empty-state compact">暂无待审核纠错</div>
      <div v-for="f in feedback" :key="f.id" class="feedback-review-card">
        <div class="feedback-review-head">
          <strong>{{ f.target_type === 'relation' ? '关系纠错' : '知识点纠错' }}</strong>
          <span>{{ f.target_id || '未指定目标' }}</span>
        </div>
        <p><b>问题说明：</b>{{ f.correction }}</p>
        <p v-if="f.correct_description"><b>建议内容：</b>{{ f.correct_description }}</p>
        <div class="form-actions">
          <button class="secondary" @click="review(f.id, 'rejected')">驳回</button>
          <button @click="review(f.id, 'approved')">通过并更新</button>
        </div>
      </div>
    </div>

    <div class="admin-section">
      <div class="section-head">
        <h4>知识冲突检测</h4>
        <button class="secondary small" @click="checkConflicts" :disabled="conflictLoading">检测</button>
      </div>
      <div v-if="conflictLoading" class="loading-spinner"></div>
      <div v-if="!conflictLoading && conflicts.length === 0" class="empty-state compact">暂未发现冲突</div>
      <div v-for="(c, i) in conflicts" :key="i" class="conflict-item" :class="c.type">
        <span class="conflict-badge">{{ { cycle: '循环', duplicate: '重复', orphan: '孤立' }[c.type] }}</span>
        <span>{{ c.name || c.node_id }}</span>
        <span class="conflict-detail">{{ c.detail }}</span>
      </div>
    </div>

    <div class="admin-section">
      <h4>用户管理</h4>
      <div class="admin-user-group">
        <h5>学生 {{ users.students?.length || 0 }}</h5>
        <div v-for="u in users.students" :key="u.id" class="admin-user-row">
          <span>{{ u.name }}</span><span class="admin-user-email">{{ u.email }}</span>
          <button @click="disable('student', u.id)" class="admin-disable-btn">禁用</button>
        </div>
      </div>
      <div class="admin-user-group">
        <h5>教师 {{ users.teachers?.length || 0 }}</h5>
        <div v-for="u in users.teachers" :key="u.id" class="admin-user-row">
          <span>{{ u.name }}</span><span class="admin-user-email">{{ u.email }}</span>
          <button @click="disable('teacher', u.id)" class="admin-disable-btn">禁用</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminApi, qaApi } from '../api/index.js'

defineEmits(['locate'])
const stats = ref({ total_nodes: 0, total_students: 0, total_teachers: 0, total_classes: 0, hot_nodes: [] })
const users = ref({ students: [], teachers: [] })
const conflicts = ref([])
const feedback = ref([])
const conflictLoading = ref(false)

async function refreshAll() {
  await fetchStats()
  await fetchFeedback()
}

async function fetchStats() {
  try { stats.value = await adminApi.dashboard() } catch {}
  try { users.value = await adminApi.listUsers() } catch {}
}

async function fetchFeedback() {
  try { feedback.value = await qaApi.listFeedback('pending') } catch { feedback.value = [] }
}

async function review(id, status) {
  try {
    await qaApi.reviewFeedback(id, status, status === 'approved' ? '审核通过' : '审核驳回')
    await fetchFeedback()
  } catch {}
}

async function checkConflicts() {
  conflictLoading.value = true
  try { conflicts.value = await adminApi.validateGraph() } catch { conflicts.value = [] }
  conflictLoading.value = false
}

async function disable(type, id) {
  try { await adminApi.disableUser(type, id); await fetchStats() } catch {}
}

onMounted(() => refreshAll())
</script>
