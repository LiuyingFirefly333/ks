<template>
  <div class="admin-dashboard">
    <AdminStatsCards :stats="stats" />
    <button class="secondary" @click="refreshAll">刷新数据</button>

    <AdminBehaviorDashboard
      :filters="behaviorFilters"
      :config="dashboardConfig"
      :config-items="dashboardConfigItems"
      :courses="dashboardCourses"
      :grades="dashboardGrades"
      :classes="filteredDashboardClasses"
      :subjects="dashboardSubjects"
      :activity="behaviorActivity"
      :knowledge-heat-top="knowledgeHeatTop"
      :question-top="questionTop"
      :class-weak-distribution="classWeakDistribution"
      :error-hot-nodes="errorHotNodes"
      :daily-activity="dailyActivity"
      :heat-width="heatWidth"
      :activity-width="activityWidth"
      @refresh="fetchStats"
      @reset-filters="resetBehaviorFilters"
      @locate="$emit('locate', $event)"
    />

    <div class="admin-section">
      <div class="section-head">
        <h4>AI 问答统计</h4>
        <button class="secondary small" @click="fetchQaStats">刷新</button>
      </div>
      <div class="qa-analytics-grid">
        <div class="qa-analytics-item"><strong>{{ qaOverview.questions || 0 }}</strong><span>提问</span></div>
        <div class="qa-analytics-item"><strong>{{ qaOverview.answers || 0 }}</strong><span>回答</span></div>
        <div class="qa-analytics-item"><strong>{{ qaOverview.feedback_pending || 0 }}</strong><span>待审核</span></div>
        <div class="qa-analytics-item"><strong>{{ qaOverview.feedback_approved || 0 }}</strong><span>已通过</span></div>
      </div>
      <div v-if="qaStats.top_sources?.length" class="qa-source-list">
        <button v-for="node in qaStats.top_sources" :key="node.node_id" class="qa-source-item" @click="$emit('locate', node.node_id)">
          <span>{{ node.name }}</span>
          <b>{{ node.count }}</b>
        </button>
      </div>
    </div>

    <AdminUserManagement
      ref="userManagementRef"
      :users="allUsers"
      :roles="roles"
      :create-form="createForm"
      :can-create="Boolean(canCreate)"
      :loading="userLoading"
      :message="userMessage"
      :error="userError"
      :format-date="formatDate"
      @trigger-import="triggerImport"
      @export-users="exportUsers"
      @import-users="importUsers"
      @create-user="createUser"
      @assign-role="assignRole"
      @disable-user="disable"
    />

    <div class="admin-section">
      <div class="section-head">
        <h4>AI 纠错审核</h4>
        <button class="secondary small" @click="fetchFeedback">刷新</button>
      </div>
      <div v-if="feedback.length === 0" class="empty-state compact">暂无待审核纠错</div>
      <div v-for="f in feedback" :key="f.id" class="feedback-review-card">
        <div class="feedback-review-head">
          <strong>{{ f.triples?.length ? '三元组纠错' : (f.target_type === 'relation' ? '关系纠错' : '知识点纠错') }}</strong>
          <span>{{ f.target_id || '未指定目标' }}</span>
        </div>
        <p><b>问题说明：</b>{{ f.correction }}</p>
        <p v-if="f.correct_description"><b>建议内容：</b>{{ f.correct_description }}</p>
        <div v-if="f.entities?.length" class="feedback-chip-row">
          <span v-for="entity in f.entities" :key="entity.id || entity.name" class="feedback-chip">{{ entity.name || entity.id }}</span>
        </div>
        <div v-if="f.triples?.length" class="feedback-triple-list">
          <div v-for="(triple, index) in f.triples" :key="index" class="feedback-triple-item">
            <span>{{ triple.source_id }}</span>
            <b>{{ triple.relation_type }}</b>
            <span>{{ triple.target_id }}</span>
            <em>{{ triple.action || 'upsert' }}</em>
          </div>
        </div>
        <div class="form-actions">
          <button class="secondary" @click="review(f.id, 'rejected')">驳回</button>
          <button @click="review(f.id, 'approved')">通过并更新</button>
        </div>
      </div>
    </div>

    <AdminGraphOps
      :hot-nodes="stats.hot_nodes || []"
      :backups="backups"
      :courses="courses"
      :conflicts="conflicts"
      v-model:incremental-course-id="incrementalCourseId"
      v-model:incremental-text="incrementalText"
      :conflict-loading="conflictLoading"
      :ops-loading="opsLoading"
      :ops-message="opsMessage"
      :format-date="formatDate"
      :conflict-label="conflictLabel"
      @locate="$emit('locate', $event)"
      @create-backup="createBackup"
      @clean-graph-data="cleanGraphData"
      @cleanup-redundant="cleanupRedundant"
      @check-conflicts="checkConflicts"
      @fix-conflict="fixConflict"
      @apply-incremental-update="applyIncrementalUpdate"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { adminApi, courseApi, qaApi } from '../api/index.js'
import AdminBehaviorDashboard from './admin/AdminBehaviorDashboard.vue'
import AdminGraphOps from './admin/AdminGraphOps.vue'
import AdminStatsCards from './admin/AdminStatsCards.vue'
import AdminUserManagement from './admin/AdminUserManagement.vue'

defineEmits(['locate'])

const roles = [
  { value: 'student', label: '学生' },
  { value: 'teacher', label: '教师' },
  { value: 'admin', label: '管理员' },
]

const defaultDashboardConfig = {
  activity: true,
  heat: true,
  questions: true,
  weak: true,
  trend: true,
  errors: true,
}
const dashboardConfigItems = [
  { key: 'activity', label: '活跃概览' },
  { key: 'heat', label: '知识热度' },
  { key: 'questions', label: '提问榜' },
  { key: 'weak', label: '薄弱分布' },
  { key: 'trend', label: '活跃趋势' },
  { key: 'errors', label: '错题考点' },
]

const stats = ref({
  total_nodes: 0,
  total_students: 0,
  total_teachers: 0,
  total_admins: 0,
  total_classes: 0,
  hot_nodes: [],
  filters: { courses: [], classes: [], grades: [], subjects: [] },
  activity: {},
  knowledge_heat_top: [],
  question_top: [],
  class_weak_distribution: [],
  error_hot_nodes: [],
  daily_activity: [],
})
const qaStats = ref({ overview: {}, events: [], daily_messages: [], top_sources: [] })
const users = ref({ students: [], teachers: [], admins: [], all: [] })
const conflicts = ref([])
const feedback = ref([])
const backups = ref([])
const courses = ref([])
const conflictLoading = ref(false)
const userLoading = ref(false)
const opsLoading = ref(false)
const userMessage = ref('')
const userError = ref('')
const opsMessage = ref('')
const userManagementRef = ref(null)
const createForm = reactive({ name: '', email: '', password: '', role: 'student' })
const behaviorFilters = reactive({
  course_id: '',
  grade: '',
  class_id: '',
  subject: '',
  days: 30,
})
const dashboardConfig = reactive(loadDashboardConfig())
const incrementalCourseId = ref('')
const incrementalText = ref('{\n  "nodes": [\n    { "name": "新知识点", "category": "增量更新", "difficulty": 1, "description": "" }\n  ],\n  "relations": []\n}')

const allUsers = computed(() => {
  if (Array.isArray(users.value.all)) return users.value.all
  return [
    ...(users.value.students || []).map(u => ({ ...u, role: 'student' })),
    ...(users.value.teachers || []).map(u => ({ ...u, role: 'teacher' })),
    ...(users.value.admins || []).map(u => ({ ...u, role: 'admin' })),
  ]
})

const canCreate = computed(() =>
  createForm.name && createForm.email && createForm.password.length >= 6 && createForm.role
)
const qaOverview = computed(() => qaStats.value.overview || {})
const dashboardFilterOptions = computed(() => stats.value.filters || {})
const dashboardCourses = computed(() => {
  const fromStats = dashboardFilterOptions.value.courses || []
  return fromStats.length ? fromStats : courses.value
})
const dashboardGrades = computed(() => dashboardFilterOptions.value.grades || [])
const dashboardSubjects = computed(() => dashboardFilterOptions.value.subjects || [])
const dashboardClasses = computed(() => dashboardFilterOptions.value.classes || [])
const filteredDashboardClasses = computed(() => dashboardClasses.value.filter(cls => (
  (!behaviorFilters.grade || cls.grade === behaviorFilters.grade)
  && (!behaviorFilters.subject || cls.subject === behaviorFilters.subject)
)))
const behaviorActivity = computed(() => stats.value.activity || {})
const knowledgeHeatTop = computed(() => stats.value.knowledge_heat_top || [])
const questionTop = computed(() => stats.value.question_top || [])
const classWeakDistribution = computed(() => stats.value.class_weak_distribution || [])
const errorHotNodes = computed(() => stats.value.error_hot_nodes || [])
const dailyActivity = computed(() => stats.value.daily_activity || [])
const maxHeat = computed(() => Math.max(1, ...knowledgeHeatTop.value.map(item => Number(item.heat || 0))))
const maxDailyActivity = computed(() => Math.max(
  1,
  ...dailyActivity.value.map(day => Number(day.qa || 0) + Number(day.attempts || 0) + Number(day.errors || 0)),
))

watch(dashboardConfig, value => {
  try {
    localStorage.setItem('admin-dashboard-config', JSON.stringify(value))
  } catch {}
}, { deep: true })

function setUserNotice(message = '', error = '') {
  userMessage.value = message
  userError.value = error
}

function loadDashboardConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem('admin-dashboard-config') || '{}')
    return { ...defaultDashboardConfig, ...saved }
  } catch {
    return { ...defaultDashboardConfig }
  }
}

function dashboardParams() {
  return Object.fromEntries(
    Object.entries(behaviorFilters)
      .filter(([, value]) => value !== '' && value !== null && value !== undefined)
  )
}

function resetBehaviorFilters() {
  behaviorFilters.course_id = ''
  behaviorFilters.grade = ''
  behaviorFilters.class_id = ''
  behaviorFilters.subject = ''
  behaviorFilters.days = 30
  fetchStats()
}

function heatWidth(value) {
  return `${Math.max(8, Math.round((Number(value || 0) / maxHeat.value) * 100))}%`
}

function activityWidth(day) {
  const total = Number(day.qa || 0) + Number(day.attempts || 0) + Number(day.errors || 0)
  return `${Math.max(6, Math.round((total / maxDailyActivity.value) * 100))}%`
}

async function refreshAll() {
  await fetchStats()
  await fetchQaStats()
  await fetchFeedback()
  await fetchBackups()
  await fetchCourses()
}

async function fetchStats() {
  try { stats.value = await adminApi.dashboard(dashboardParams()) } catch {}
  try { users.value = await adminApi.listUsers() } catch {}
}

async function fetchFeedback() {
  try { feedback.value = await qaApi.listFeedback('pending') } catch { feedback.value = [] }
}

async function fetchQaStats() {
  try { qaStats.value = await qaApi.analytics(30) } catch { qaStats.value = { overview: {}, events: [], daily_messages: [], top_sources: [] } }
}

async function fetchBackups() {
  try { backups.value = await adminApi.listGraphBackups() } catch { backups.value = [] }
}

async function fetchCourses() {
  try {
    courses.value = await courseApi.list()
    if (!incrementalCourseId.value && courses.value.length) incrementalCourseId.value = courses.value[0].id
  } catch {
    courses.value = []
  }
}

async function createUser() {
  if (!canCreate.value) return
  userLoading.value = true
  setUserNotice()
  try {
    await adminApi.createUser({ ...createForm })
    createForm.name = ''
    createForm.email = ''
    createForm.password = ''
    createForm.role = 'student'
    setUserNotice('账号已创建')
    await fetchStats()
  } catch (error) {
    setUserNotice('', error.normalizedMessage || '创建失败')
  } finally {
    userLoading.value = false
  }
}

async function assignRole(user, role) {
  if (!role || role === user.role) return
  userLoading.value = true
  setUserNotice()
  try {
    await adminApi.assignUserRole(user.role, user.id, role)
    setUserNotice('角色已更新')
    await fetchStats()
  } catch (error) {
    setUserNotice('', error.normalizedMessage || '角色更新失败')
    await fetchStats()
  } finally {
    userLoading.value = false
  }
}

async function disable(type, id) {
  userLoading.value = true
  setUserNotice()
  try {
    await adminApi.disableUser(type, id)
    setUserNotice('账号已禁用')
    await fetchStats()
  } catch (error) {
    setUserNotice('', error.normalizedMessage || '禁用失败')
  } finally {
    userLoading.value = false
  }
}

function triggerImport() {
  userManagementRef.value?.openImportDialog()
}

async function importUsers(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  userLoading.value = true
  setUserNotice()
  try {
    const usersToImport = parseCsv(await file.text())
    if (!usersToImport.length) {
      setUserNotice('', 'CSV 中没有可导入的账号')
      return
    }
    const data = await adminApi.importUsers(usersToImport)
    const result = data.result || {}
    setUserNotice(`导入完成：新增 ${result.created_count || 0}，跳过 ${result.skipped_count || 0}，错误 ${result.error_count || 0}`)
    await fetchStats()
  } catch (error) {
    setUserNotice('', error.normalizedMessage || '导入失败')
  } finally {
    userLoading.value = false
  }
}

async function exportUsers() {
  userLoading.value = true
  setUserNotice()
  try {
    const blob = await adminApi.exportUsers()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `users-${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
    setUserNotice('用户数据已导出')
  } catch (error) {
    setUserNotice('', error.normalizedMessage || '导出失败')
  } finally {
    userLoading.value = false
  }
}

function parseCsv(text) {
  const rows = text.split(/\r?\n/).filter(line => line.trim()).map(parseCsvLine)
  if (!rows.length) return []
  const headers = rows.shift().map(h => h.replace(/^\uFEFF/, '').trim().toLowerCase())
  return rows.map(cols => {
    const row = {}
    headers.forEach((header, index) => { row[header] = (cols[index] || '').trim() })
    return {
      name: row.name || row['姓名'] || '',
      email: row.email || row['邮箱'] || '',
      password: row.password || row['密码'] || '',
      role: normalizeRole(row.role || row['角色'] || ''),
    }
  }).filter(row => row.name || row.email)
}

function parseCsvLine(line) {
  const cols = []
  let current = ''
  let quoted = false
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i]
    const next = line[i + 1]
    if (char === '"' && quoted && next === '"') {
      current += '"'
      i += 1
    } else if (char === '"') {
      quoted = !quoted
    } else if (char === ',' && !quoted) {
      cols.push(current)
      current = ''
    } else {
      current += char
    }
  }
  cols.push(current)
  return cols
}

function normalizeRole(role) {
  const value = String(role).trim().toLowerCase()
  return ({ 学生: 'student', 教师: 'teacher', 管理员: 'admin' }[value] || value)
}

function formatDate(value) {
  if (!value) return ''
  return String(value).slice(0, 10)
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

function conflictLabel(conflict) {
  if (conflict.type === 'cycle') return '循环'
  if (conflict.type === 'duplicate') return '重复'
  if (conflict.type === 'orphan') return '孤立'
  if (conflict.type === 'chapter_assignment') return '归属'
  if (conflict.type === 'relation_logic') return '关系'
  return '问题'
}

async function fixConflict(conflict) {
  if (!conflict.fixable) return
  opsLoading.value = true
  opsMessage.value = ''
  try {
    const result = await adminApi.fixGraphIssue(conflict)
    opsMessage.value = result.message || `已修复 ${result.fixed || 0} 项`
    await checkConflicts()
    await fetchStats()
  } catch (error) {
    opsMessage.value = error.normalizedMessage || '修复失败'
  } finally {
    opsLoading.value = false
  }
}

async function createBackup() {
  opsLoading.value = true
  opsMessage.value = ''
  try {
    const data = await adminApi.createGraphBackup(`手动备份 ${new Date().toLocaleString()}`)
    opsMessage.value = `备份完成：${data.backup?.node_count || 0} 节点，${data.backup?.relation_count || 0} 关系`
    await fetchBackups()
  } catch (error) {
    opsMessage.value = error.normalizedMessage || '备份失败'
  } finally {
    opsLoading.value = false
  }
}

async function cleanGraphData() {
  opsLoading.value = true
  opsMessage.value = ''
  try {
    const data = await adminApi.cleanGraphData()
    const result = data.result || {}
    opsMessage.value = `清洗完成：${result.nodes || 0} 知识点，${result.resources || 0} 资源，${result.relations || 0} 关系`
    await checkConflicts()
  } catch (error) {
    opsMessage.value = error.normalizedMessage || '数据清洗失败'
  } finally {
    opsLoading.value = false
  }
}

async function cleanupRedundant() {
  if (!confirm('将合并同名冗余知识点，并迁移其关系、资源、题目和掌握记录。是否继续？')) return
  opsLoading.value = true
  opsMessage.value = ''
  try {
    const data = await adminApi.cleanupRedundantNodes()
    const result = data.result || {}
    opsMessage.value = `冗余清理完成：处理 ${result.groups || 0} 组，合并 ${result.merged || 0} 个节点`
    await checkConflicts()
    await fetchStats()
  } catch (error) {
    opsMessage.value = error.normalizedMessage || '冗余清理失败'
  } finally {
    opsLoading.value = false
  }
}

async function applyIncrementalUpdate() {
  opsLoading.value = true
  opsMessage.value = ''
  try {
    const parsed = JSON.parse(incrementalText.value)
    const payload = Array.isArray(parsed)
      ? { nodes: parsed, relations: [] }
      : { nodes: parsed.nodes || [], relations: parsed.relations || [] }
    const data = await adminApi.incrementalUpdate({
      course_id: incrementalCourseId.value,
      nodes: payload.nodes,
      relations: payload.relations,
    })
    const result = data.result || {}
    opsMessage.value = `增量更新完成：${result.created_nodes || 0} 知识点，${result.created_relations || 0} 关系；已自动备份`
    await fetchBackups()
    await checkConflicts()
    await fetchStats()
  } catch (error) {
    opsMessage.value = error.normalizedMessage || error.message || '增量更新失败'
  } finally {
    opsLoading.value = false
  }
}

onMounted(() => refreshAll())
</script>
