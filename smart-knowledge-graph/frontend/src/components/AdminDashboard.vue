<template>
  <div class="admin-dashboard">
    <div class="admin-stats">
      <div class="stat-card"><div class="stat-num">{{ stats.total_nodes }}</div><div class="stat-label">知识点</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_students }}</div><div class="stat-label">学生</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_teachers }}</div><div class="stat-label">教师</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_admins || 0 }}</div><div class="stat-label">管理员</div></div>
      <div class="stat-card"><div class="stat-num">{{ stats.total_classes }}</div><div class="stat-label">班级</div></div>
    </div>
    <button class="secondary" @click="refreshAll">刷新数据</button>

    <div class="admin-section behavior-dashboard">
      <div class="section-head">
        <h4>学习行为数据大屏</h4>
        <div class="admin-section-actions">
          <button class="secondary small" @click="resetBehaviorFilters">重置筛选</button>
          <button class="secondary small" @click="fetchStats">刷新大屏</button>
        </div>
      </div>

      <div class="dashboard-filter-bar">
        <div class="form-row">
          <label>课程</label>
          <select v-model="behaviorFilters.course_id" @change="fetchStats">
            <option value="">全部课程</option>
            <option v-for="course in dashboardCourses" :key="course.id" :value="course.id">{{ course.name }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>年级</label>
          <select v-model="behaviorFilters.grade" @change="fetchStats">
            <option value="">全部年级</option>
            <option v-for="grade in dashboardGrades" :key="grade" :value="grade">{{ grade }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>班级</label>
          <select v-model="behaviorFilters.class_id" @change="fetchStats">
            <option value="">全部班级</option>
            <option v-for="cls in filteredDashboardClasses" :key="cls.id" :value="cls.id">{{ cls.name }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>学科</label>
          <select v-model="behaviorFilters.subject" @change="fetchStats">
            <option value="">全部学科</option>
            <option v-for="subject in dashboardSubjects" :key="subject" :value="subject">{{ subject }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>时间</label>
          <select v-model.number="behaviorFilters.days" @change="fetchStats">
            <option :value="7">近 7 天</option>
            <option :value="30">近 30 天</option>
            <option :value="90">近 90 天</option>
            <option :value="180">近 180 天</option>
          </select>
        </div>
      </div>

      <div class="dashboard-config">
        <label v-for="item in dashboardConfigItems" :key="item.key" class="dashboard-toggle">
          <input v-model="dashboardConfig[item.key]" type="checkbox" />
          <span>{{ item.label }}</span>
        </label>
      </div>

      <div v-if="dashboardConfig.activity" class="qa-analytics-grid behavior-metric-grid">
        <div class="qa-analytics-item"><strong>{{ behaviorActivity.qa_questions || 0 }}</strong><span>学生提问</span></div>
        <div class="qa-analytics-item"><strong>{{ behaviorActivity.practice_attempts || 0 }}</strong><span>答题尝试</span></div>
        <div class="qa-analytics-item"><strong>{{ behaviorActivity.error_records || 0 }}</strong><span>新增错题</span></div>
        <div class="qa-analytics-item"><strong>{{ behaviorActivity.active_students || 0 }}</strong><span>活跃学生</span></div>
      </div>

      <div class="dashboard-panel-grid">
        <div v-if="dashboardConfig.heat" class="dashboard-panel wide">
          <div class="panel-title-row">
            <h5>知识点访问热度 TOP</h5>
            <span>{{ behaviorFilters.days }} 天</span>
          </div>
          <div v-if="!knowledgeHeatTop.length" class="empty-state compact">暂无行为热度数据</div>
          <button
            v-for="node in knowledgeHeatTop"
            :key="node.node_id"
            class="heat-rank-row"
            @click="$emit('locate', node.node_id)"
          >
            <span class="heat-rank-name">{{ node.name }}</span>
            <span class="heat-rank-bar"><i :style="{ width: heatWidth(node.heat) }"></i></span>
            <b>{{ node.heat }}</b>
            <small>问 {{ node.qa_count }} · 练 {{ node.attempt_count }} · 错 {{ node.error_count }}</small>
          </button>
        </div>

        <div v-if="dashboardConfig.questions" class="dashboard-panel">
          <div class="panel-title-row">
            <h5>高频提问榜</h5>
            <span>AI 来源引用</span>
          </div>
          <div v-if="!questionTop.length" class="empty-state compact">暂无高频提问数据</div>
          <button v-for="node in questionTop" :key="node.node_id" class="compact-rank-row" @click="$emit('locate', node.node_id)">
            <span>{{ node.name }}</span>
            <b>{{ node.qa_count }}</b>
          </button>
        </div>

        <div v-if="dashboardConfig.errors" class="dashboard-panel">
          <div class="panel-title-row">
            <h5>错题高频考点</h5>
            <span>错题本</span>
          </div>
          <div v-if="!errorHotNodes.length" class="empty-state compact">暂无错题考点数据</div>
          <button v-for="node in errorHotNodes" :key="node.node_id" class="compact-rank-row danger" @click="$emit('locate', node.node_id)">
            <span>{{ node.name }}</span>
            <b>{{ node.error_count }}</b>
          </button>
        </div>

        <div v-if="dashboardConfig.weak" class="dashboard-panel">
          <div class="panel-title-row">
            <h5>班级薄弱分布</h5>
            <span>低掌握 + 错题</span>
          </div>
          <div v-if="!classWeakDistribution.length" class="empty-state compact">暂无班级薄弱数据</div>
          <div v-for="cls in classWeakDistribution" :key="cls.class_id" class="class-weak-row">
            <div>
              <strong>{{ cls.class_name }}</strong>
              <small>{{ cls.grade || '未分级' }} · {{ cls.subject || '未分科' }} · {{ cls.student_count || 0 }} 人</small>
            </div>
            <span>薄弱 {{ cls.weak_count || 0 }}</span>
            <b>{{ cls.avg_score || 0 }}</b>
          </div>
        </div>

        <div v-if="dashboardConfig.trend" class="dashboard-panel">
          <div class="panel-title-row">
            <h5>活跃统计</h5>
            <span>日趋势</span>
          </div>
          <div v-if="!dailyActivity.length" class="empty-state compact">暂无活跃趋势数据</div>
          <div v-for="day in dailyActivity" :key="day.date" class="daily-activity-row">
            <span>{{ day.date?.slice(5) }}</span>
            <i :style="{ width: activityWidth(day) }"></i>
            <small>问 {{ day.qa || 0 }} · 练 {{ day.attempts || 0 }} · 错 {{ day.errors || 0 }}</small>
          </div>
        </div>
      </div>
    </div>

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

    <div class="admin-section">
      <div class="section-head">
        <h4>用户管理</h4>
        <div class="admin-section-actions">
          <button class="secondary small" @click="triggerImport">导入 CSV</button>
          <button class="secondary small" @click="exportUsers">导出 CSV</button>
          <input ref="importInput" type="file" accept=".csv,text/csv" class="hidden-file-input" @change="importUsers" />
        </div>
      </div>

      <div class="admin-user-form">
        <div class="form-row">
          <label>姓名</label>
          <input v-model.trim="createForm.name" placeholder="例如：王同学" />
        </div>
        <div class="form-row">
          <label>邮箱</label>
          <input v-model.trim="createForm.email" type="email" placeholder="name@example.com" />
        </div>
        <div class="form-row">
          <label>初始密码</label>
          <input v-model="createForm.password" type="password" placeholder="至少 6 位" />
        </div>
        <div class="form-row">
          <label>角色</label>
          <select v-model="createForm.role">
            <option v-for="role in roles" :key="role.value" :value="role.value">{{ role.label }}</option>
          </select>
        </div>
        <button @click="createUser" :disabled="userLoading || !canCreate">新增账号</button>
      </div>

      <div v-if="userMessage" class="inline-hint">{{ userMessage }}</div>
      <div v-if="userError" class="inline-error">{{ userError }}</div>

      <div v-if="allUsers.length === 0" class="empty-state compact">暂无用户</div>
      <div v-else class="admin-user-table">
        <div class="admin-user-table-head">
          <span>账号</span>
          <span>邮箱</span>
          <span>角色</span>
          <span>状态</span>
          <span>操作</span>
        </div>
        <div v-for="u in allUsers" :key="u.role + '-' + u.id" class="admin-user-row" :class="{ disabled: u.disabled }">
          <div class="admin-user-main">
            <strong>{{ u.name }}</strong>
            <small>{{ formatDate(u.created_at) || u.id }}</small>
          </div>
          <span class="admin-user-email">{{ u.email }}</span>
          <select class="admin-role-select" :value="u.role" :disabled="userLoading || u.disabled" @change="assignRole(u, $event.target.value)">
            <option v-for="role in roles" :key="role.value" :value="role.value">{{ role.label }}</option>
          </select>
          <span class="admin-status-badge" :class="{ disabled: u.disabled }">{{ u.disabled ? '已禁用' : '正常' }}</span>
          <button
            class="admin-disable-btn"
            :disabled="userLoading || u.disabled"
            @click="disable(u.role, u.id)"
          >
            禁用
          </button>
        </div>
      </div>
    </div>

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

    <div class="admin-section">
      <div class="section-head">
        <h4>知识库运维</h4>
        <div class="admin-section-actions">
          <button class="secondary small" @click="createBackup" :disabled="opsLoading">版本备份</button>
          <button class="secondary small" @click="cleanGraphData" :disabled="opsLoading">数据清洗</button>
          <button class="secondary small" @click="cleanupRedundant" :disabled="opsLoading">冗余清理</button>
          <button class="secondary small" @click="checkConflicts" :disabled="conflictLoading">冲突检测</button>
        </div>
      </div>
      <div v-if="opsMessage" class="inline-hint">{{ opsMessage }}</div>

      <div class="ops-grid">
        <div class="ops-card">
          <h5>版本备份</h5>
          <div v-if="!backups.length" class="empty-state compact">暂无备份</div>
          <div v-for="backup in backups.slice(0, 4)" :key="backup.id" class="backup-row">
            <span>{{ backup.label || '知识库备份' }}</span>
            <small>{{ formatDate(backup.created_at) }} · {{ backup.node_count || 0 }} 节点 · {{ backup.relation_count || 0 }} 关系</small>
          </div>
        </div>

        <div class="ops-card">
          <h5>增量更新</h5>
          <div class="form-row">
            <label>目标课程</label>
            <select v-model="incrementalCourseId">
              <option value="">选择课程</option>
              <option v-for="course in courses" :key="course.id" :value="course.id">{{ course.name }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>JSON 数据</label>
            <textarea v-model.trim="incrementalText" rows="6" placeholder='{"nodes":[{"name":"知识点A"}],"relations":[]}'></textarea>
          </div>
          <button class="full-width" @click="applyIncrementalUpdate" :disabled="opsLoading || !incrementalCourseId || !incrementalText">应用增量更新</button>
        </div>
      </div>

      <div v-if="conflictLoading" class="loading-spinner"></div>
      <div v-if="!conflictLoading && conflicts.length === 0" class="empty-state compact">暂未发现冲突</div>
      <div v-for="(c, i) in conflicts" :key="i" class="conflict-item" :class="c.type">
        <span class="conflict-badge">{{ conflictLabel(c) }}</span>
        <span class="conflict-name">{{ c.name || c.node_id || c.source_id }}</span>
        <span class="conflict-detail">{{ c.detail }}</span>
        <button class="secondary small" @click="fixConflict(c)" :disabled="opsLoading || !c.fixable">修复</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { adminApi, courseApi, qaApi } from '../api/index.js'

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
const importInput = ref(null)
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
  importInput.value?.click()
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
