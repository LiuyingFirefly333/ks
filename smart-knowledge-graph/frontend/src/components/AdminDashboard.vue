<template>
  <div class="admin-dashboard">
    <!-- 统计卡片 -->
    <div class="admin-stats">
      <div class="stat-card"><div class="stat-num">{{ stats.total_nodes }}</div><div class="stat-label">知识点</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_students }}</div><div class="stat-label">学生</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_teachers }}</div><div class="stat-label">教师</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_classes }}</div><div class="stat-label">班级</div></div>
    </div>
    <button @click="fetchStats" style="font-size:12px;padding:4px 12px;margin-bottom:8px">刷新</button>

    <!-- 热点知识点 -->
    <div v-if="stats.hot_nodes?.length" class="admin-section">
      <h4>热点知识点 TOP 10</h4>
      <div v-for="h in stats.hot_nodes" :key="h.node_id" class="admin-hot-row">
        <span class="admin-hot-name" @click="$emit('locate', h.node_id)">{{ h.name }}</span>
        <span class="admin-hot-meta">{{ h.assess_count }}人 | 均分{{ h.avg_score }}</span>
      </div>
    </div>

    <!-- 知识冲突检测 -->
    <div class="admin-section">
      <h4>知识冲突检测 <button @click="checkConflicts" :disabled="conflictLoading" style="font-size:10px;padding:2px 8px">检测</button></h4>
      <div v-if="conflictLoading" class="loading-spinner"></div>
      <div v-if="!conflictLoading && conflicts.length === 0" class="empty-state" style="padding:8px">暂未发现冲突</div>
      <div v-for="(c, i) in conflicts" :key="i" class="conflict-item" :class="c.type">
        <span class="conflict-badge">{{ {cycle:'循环',duplicate:'重复',orphan:'孤立'}[c.type] }}</span>
        <span>{{ c.name || c.node_id }}</span>
        <span class="conflict-detail">{{ c.detail }}</span>
      </div>
    </div>

    <!-- 用户管理 -->
    <div class="admin-section">
      <h4>用户管理</h4>
      <div class="admin-user-group">
        <h5>学生 ({{ users.students?.length || 0 }})</h5>
        <div v-for="u in users.students" :key="u.id" class="admin-user-row">
          <span>{{ u.name }}</span><span class="admin-user-email">{{ u.email }}</span>
          <button @click="disable('student', u.id)" class="admin-disable-btn">禁用</button>
        </div>
      </div>
      <div class="admin-user-group">
        <h5>教师 ({{ users.teachers?.length || 0 }})</h5>
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
import { adminApi } from '../api/index.js'

const emit = defineEmits(['locate'])
const stats = ref({ total_nodes: 0, total_students: 0, total_teachers: 0, total_classes: 0, hot_nodes: [] })
const users = ref({ students: [], teachers: [] })
const conflicts = ref([])
const conflictLoading = ref(false)

async function fetchStats() {
  try { stats.value = await adminApi.dashboard() } catch {}
  try { users.value = await adminApi.listUsers() } catch {}
}

async function checkConflicts() {
  conflictLoading.value = true
  try { conflicts.value = await adminApi.validateGraph() } catch { conflicts.value = [] }
  conflictLoading.value = false
}

async function disable(type, id) {
  try { await adminApi.disableUser(type, id); await fetchStats() } catch {}
}

onMounted(() => fetchStats())
</script>