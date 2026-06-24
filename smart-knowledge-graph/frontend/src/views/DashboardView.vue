<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-brand">
        <span class="brand-mark">KG</span>
        <div>
          <div class="brand-text">智能知识图谱学习系统</div>
          <div class="brand-subtitle">Knowledge Graph Learning Workspace</div>
        </div>
      </div>

      <nav class="topbar-center topnav" aria-label="功能选项">
        <button
          v-for="item in navItems"
          :key="item.key"
          class="topnav-item"
          :class="{ active: activeNav === item.key }"
          :title="item.hint"
          @click="onNavClick(item.key)"
        >
          <span class="topnav-icon">{{ item.icon }}</span>
          <span class="topnav-label">{{ item.label }}</span>
        </button>
      </nav>

      <div class="topbar-user">
        <span class="user-role-badge">{{ roleLabel }}</span>
        <span class="user-name">{{ user?.name || '未命名用户' }}</span>
        <button class="ghost-button" @click="activeNav = 'profile'">个人中心</button>
        <button class="ghost-button" @click="$emit('logout')">退出</button>
      </div>
    </header>

    <div class="app-body">
      <aside class="course-sidebar">
        <div class="course-sidebar-head">
          <div>
            <span class="sidebar-eyebrow">课程</span>
            <h2>学习课程</h2>
          </div>
          <span class="course-count">{{ courses.length }}</span>
        </div>

        <div v-if="!courses.length" class="empty-state compact">暂无课程</div>

        <div v-else class="course-list">
          <button
            v-for="c in courses"
            :key="c.id"
            class="course-item"
            :class="{ active: currentCourseId === c.id }"
            :title="c.name"
            @click="selectCourse(c.id)"
          >
            <span class="course-name">{{ c.name }}</span>
            <span v-if="currentCourseId === c.id" class="course-status">当前</span>
          </button>
        </div>

        <div v-if="user?.role === 'teacher'" class="sidebar-controls">
          <div class="form-row">
            <label>班级视图</label>
            <select v-model="currentClassId" @change="onClassChange" class="sidebar-select">
              <option value="">全部班级</option>
              <option v-for="c in classes" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>

          <button
            class="soft-button full-width"
            :class="{ active: heatmapMode }"
            @click="toggleHeatmap"
          >
            {{ heatmapMode ? '关闭热力图' : '班级热力图' }}
          </button>
        </div>
      </aside>

      <main class="main-content">
        <div class="graph-stage">
          <KnowledgeGraph
            ref="graphRef"
            :nodes="nodes"
            :links="links"
            :highlightedPath="highlightedPath"
            :searchNodeId="searchNodeId"
            :selectedNodeId="selectedNode?.id"
            :masteryMap="masteryMap"
            :heatmapData="heatmapData"
            :heatmapMode="heatmapMode"
            @select-node="onSelectNode"
          />
          <div v-if="!currentCourseId" class="graph-empty">
            <div class="empty-kicker">等待课程</div>
            <h2>选择一门课程开始浏览知识图谱</h2>
            <p>课程加载后会展示知识点、前置关系、掌握度与推荐路径。</p>
          </div>
        </div>

        <div class="floating-tools">
          <button title="适应画布" @click="fitGraph">适应</button>
          <button title="放大" @click="zoomIn">+</button>
          <button title="缩小" @click="zoomOut">-</button>
        </div>

        <div class="floating-legend">
          <div class="legend-title">图例</div>
          <div class="legend-row"><span class="ldot" style="background:#2563eb"></span>知识点</div>
          <div class="legend-row"><span class="ldot" style="background:#16a34a"></span>熟练</div>
          <div class="legend-row"><span class="ldot" style="background:#f59e0b"></span>一般</div>
          <div class="legend-row"><span class="ldot" style="background:#f97316"></span>薄弱</div>
          <div class="legend-row"><span style="display:inline-block;width:18px;height:2px;background:#ef4444"></span>推荐路径</div>
          <div class="legend-row"><span style="display:inline-block;width:18px;height:0;border-top:2px dashed #94a3b8"></span>相关概念</div>
        </div>
      </main>

      <aside v-if="selectedNode" class="slide-panel">
        <KnowledgePanel
          :node="selectedNode"
          :userId="user?.id || ''"
          :userRole="user?.role || 'student'"
          @close="selectedNode = null; onClearPath()"
          @locate="onLocateNode"
          @show-roadmap="onShowRoadmap"
          @ask-ai="onAskAI"
        />
      </aside>
    </div>

    <div v-if="activeNav !== 'graph'" class="bottom-drawer">
      <div class="drawer-handle" @click="activeNav = 'graph'">
        <div>
          <span class="drawer-title">{{ currentNavLabel }}</span>
          <span class="drawer-subtitle">{{ currentNavHint }}</span>
        </div>
        <span class="drawer-close">收起</span>
      </div>

      <div class="drawer-body">
        <div v-if="activeNav === 'browse'" class="drawer-scroll">
          <KnowledgeSearch v-if="currentCourseId" :courseId="currentCourseId" @locate="onLocateNode" />
          <div class="cat-selector" v-if="currentCourseId && categories.length">
            <button :class="{ active: !selectedCategory }" @click="selectedCategory = ''; fetchGraph()">全部</button>
            <button
              v-for="cat in categories"
              :key="cat"
              :class="{ active: selectedCategory === cat }"
              @click="selectedCategory = cat; fetchGraph()"
            >
              {{ displayCategory(cat) }}
            </button>
          </div>
          <div v-if="!currentCourseId" class="empty-state">请先选择课程</div>
          <div class="node-list" v-else>
            <div v-for="n in nodes" :key="n.id" class="node-card" @click="onSelectNode(n)">
              <div class="node-card-left" :style="{ borderLeftColor: getColor(n.category) }">
                <span class="node-card-name">{{ n.name }}</span>
                <span class="node-card-cat">{{ displayCategory(n.category) }}</span>
              </div>
              <span v-if="n.estimated_time" class="node-card-time">{{ n.estimated_time }} 分钟</span>
            </div>
          </div>
        </div>

        <div v-if="activeNav === 'qa'" class="drawer-scroll drawer-chat">
          <ChatPanel
            :courseId="currentCourseId"
            :focusedNode="focusedNode"
            @locate="onLocateNode"
            @clear-focus="onClearFocus"
          />
        </div>

        <div v-if="activeNav === 'path'" class="drawer-scroll">
          <PathRecommend
            ref="pathRecommendRef"
            :studentId="user?.id || ''"
            :targetNode="selectedNode"
            :masteredIds="masteredIds"
            @locate="onLocateNode"
            @clear="onClearPath"
            @path-found="onPathFound"
          />
        </div>

        <div v-if="activeNav === 'errors'" class="drawer-scroll">
          <ErrorBook :studentId="user?.id" @locate-node="onLocateErrorNode" />
        </div>

        <div v-if="activeNav === 'paper'" class="drawer-scroll">
          <TestPaper :studentId="user?.id" :courseId="currentCourseId" @locate-node="onLocateErrorNode" />
        </div>

        <div v-if="activeNav === 'profile'" class="drawer-scroll">
          <ProfileCenter
            :user="user"
            :courseId="currentCourseId"
            @updated="$emit('profile-updated', $event)"
            @locate="onLocateNodeId"
          />
        </div>

        <div v-if="activeNav === 'admin'" class="drawer-scroll">
          <AdminDashboard @locate="onLocateNodeId" />
        </div>

        <div v-if="activeNav === 'manage'" class="drawer-scroll">
          <div class="manage-grid">
            <section class="manage-form">
              <h3>知识点维护</h3>
              <div class="form-row">
                <label>知识点名称</label>
                <input v-model="form.name" placeholder="例如：导数的概念" />
              </div>
              <div class="form-row">
                <label>分类</label>
                <input v-model="form.category" placeholder="例如：高等数学-导数" />
              </div>
              <div class="form-row two-cols">
                <div>
                  <label>难度</label>
                  <input v-model.number="form.difficulty" type="number" min="1" max="5" />
                </div>
                <div>
                  <label>预计时长</label>
                  <input v-model.number="form.estimated_time" type="number" min="0" placeholder="分钟" />
                </div>
              </div>
              <div class="form-row">
                <label>描述</label>
                <textarea v-model="form.description" rows="3" placeholder="补充知识点说明"></textarea>
              </div>
              <div class="form-actions">
                <button @click="onCreateNode" :disabled="!form.name">创建知识点</button>
                <button v-if="selectedNode" class="danger" @click="onDeleteNode">删除选中</button>
              </div>
            </section>

            <section class="manage-form">
              <h3>关系维护</h3>
              <div class="form-row">
                <label>源知识点</label>
                <select v-model="relSource">
                  <option value="">请选择</option>
                  <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
                </select>
              </div>
              <div class="form-row">
                <label>目标知识点</label>
                <select v-model="relTarget">
                  <option value="">请选择</option>
                  <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
                </select>
              </div>
              <div class="form-row">
                <label>关系类型</label>
                <select v-model="relType">
                  <option value="PREREQUISITE">前置知识</option>
                  <option value="RELATED_TO">相关概念</option>
                </select>
              </div>
              <button @click="onCreateRelation" :disabled="!relSource || !relTarget">建立关系</button>
            </section>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { knowledgeApi, graphApi, courseApi, analyticsApi, classroomApi } from '../api/index.js'
import KnowledgeGraph from '../components/KnowledgeGraph.vue'
import KnowledgeSearch from '../components/KnowledgeSearch.vue'
import KnowledgePanel from '../components/KnowledgePanel.vue'
import PathRecommend from '../components/PathRecommend.vue'
import ChatPanel from '../components/ChatPanel.vue'
import ErrorBook from '../components/ErrorBook.vue'
import TestPaper from '../components/TestPaper.vue'
import AdminDashboard from '../components/AdminDashboard.vue'
import ProfileCenter from '../components/ProfileCenter.vue'

const props = defineProps({ user: { type: Object, default: null } })
defineEmits(['logout', 'profile-updated'])

const roleLabel = computed(() => ({ student: '学生', teacher: '教师', admin: '管理员' }[props.user?.role] || '学生'))

const navItems = computed(() => {
  const items = [
    { key: 'graph', icon: 'KG', label: '知识图谱', hint: '全局关系视图' },
    { key: 'browse', icon: 'BR', label: '知识浏览', hint: '搜索与筛选节点' },
    { key: 'qa', icon: 'AI', label: 'AI 问答', hint: '结合图谱上下文答疑' },
    { key: 'path', icon: 'PT', label: '学习路径', hint: '推荐补习路线' },
    { key: 'errors', icon: 'ER', label: '错题本', hint: '错题溯源分析' },
    { key: 'paper', icon: 'EX', label: '智能组卷', hint: '薄弱点专项训练' },
    { key: 'profile', icon: 'ME', label: '个人中心', hint: '资料编辑与学习概览' },
  ]
  if (props.user?.role === 'admin') {
    items.push({ key: 'admin', icon: 'AD', label: '数据看板', hint: '平台与知识库运营' })
  }
  if (props.user?.role === 'teacher' || props.user?.role === 'admin') {
    items.push({ key: 'manage', icon: 'MG', label: '知识管理', hint: '维护节点与关系' })
  }
  return items
})

const currentNavLabel = computed(() => navItems.value.find(n => n.key === activeNav.value)?.label || '')
const currentNavHint = computed(() => navItems.value.find(n => n.key === activeNav.value)?.hint || '')

const graphRef = ref(null)
const pathRecommendRef = ref(null)
const activeNav = ref('graph')
const nodes = ref([])
const links = ref([])
const categories = ref([])
const selectedCategory = ref('')
const selectedNode = ref(null)
const highlightedPath = ref([])
const searchNodeId = ref(null)
const courses = ref([])
const currentCourseId = ref('')
const currentClassId = ref('')
const masteryMap = ref({})
const classes = ref([])
const heatmapData = ref([])
const heatmapMode = ref(false)
const masteredIds = ref([])
const focusedNode = ref(null)
const form = ref({ name: '', category: '', difficulty: 1, estimated_time: 0, description: '' })
const relSource = ref('')
const relTarget = ref('')
const relType = ref('PREREQUISITE')

function displayCategory(cat) {
  if (!cat) return '未分类'
  return String(cat).split('-').pop()
}

function getColor(cat) {
  const palette = ['#2563eb', '#16a34a', '#f59e0b', '#0891b2', '#dc2626', '#7c3aed', '#0f766e']
  const key = String(cat || '')
  let hash = 0
  for (let i = 0; i < key.length; i++) hash = (hash + key.charCodeAt(i) * (i + 1)) % palette.length
  return palette[hash]
}

function onNavClick(key) {
  activeNav.value = activeNav.value === key && key !== 'graph' ? 'graph' : key
}

async function selectCourse(courseId) {
  if (currentCourseId.value === courseId) return
  currentCourseId.value = courseId
  await onCourseChange()
}

async function fetchGraph() {
  if (!currentCourseId.value) {
    nodes.value = []
    links.value = []
    return
  }
  try {
    const data = await graphApi.getGraph(selectedCategory.value || undefined, currentCourseId.value, props.user?.id)
    nodes.value = data.nodes || []
    links.value = data.links || []
  } catch (e) {
    console.error('加载知识图谱失败', e)
  }
}

async function fetchCategories() {
  if (!currentCourseId.value) {
    categories.value = []
    return
  }
  try {
    categories.value = await graphApi.getCategories(currentCourseId.value)
  } catch {
    categories.value = []
  }
}

async function fetchCourses() {
  try {
    courses.value = await courseApi.list()
    if (!currentCourseId.value && courses.value.length) {
      currentCourseId.value = courses.value[0].id
      await onCourseChange()
    }
  } catch {
    courses.value = []
  }
}

async function fetchClasses() {
  if (props.user?.role === 'teacher') {
    try {
      classes.value = await classroomApi.listClasses(props.user.id)
    } catch {
      classes.value = []
    }
  }
}

async function fetchMastery() {
  if (!props.user?.id || !currentCourseId.value) return
  try {
    const data = await analyticsApi.calcMastery(props.user.id, currentCourseId.value)
    const map = {}
    for (const n of (data.nodes || [])) map[n.node_id] = { score: n.score, level: n.level }
    masteryMap.value = map
    masteredIds.value = Object.entries(map).filter(([, v]) => v.score >= 70).map(([id]) => id)
  } catch {
    masteryMap.value = {}
  }
}

async function onCourseChange() {
  selectedNode.value = null
  highlightedPath.value = []
  selectedCategory.value = ''
  await fetchGraph()
  await fetchCategories()
  await fetchMastery()
}

async function onClassChange() {
  if (heatmapMode.value) await fetchHeatmap()
}

async function toggleHeatmap() {
  heatmapMode.value = !heatmapMode.value
  if (heatmapMode.value && currentClassId.value) await fetchHeatmap()
  else {
    heatmapData.value = []
    await fetchGraph()
  }
}

async function fetchHeatmap() {
  if (!currentClassId.value || !currentCourseId.value) return
  try {
    const data = await analyticsApi.classHeatmap(currentClassId.value, currentCourseId.value)
    heatmapData.value = data.nodes || []
    await fetchGraph()
  } catch {
    heatmapData.value = []
  }
}

function onSelectNode(node) {
  selectedNode.value = node
  searchNodeId.value = null
}

function onLocateNode(node) {
  selectedNode.value = node
  searchNodeId.value = node.id
  if (graphRef.value) graphRef.value.locateNode(node.id)
}

function onLocateNodeId(nodeId) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (node) onLocateNode(node)
}

function onLocateErrorNode(nodeId) {
  onLocateNodeId(nodeId)
}

function onPathFound(pathNodes) {
  highlightedPath.value = pathNodes.map(n => n.id)
}

function onShowRoadmap(targetId) {
  activeNav.value = 'path'
  if (pathRecommendRef.value) pathRecommendRef.value.fetchPath(targetId)
}

function onClearPath() {
  highlightedPath.value = []
}

function onAskAI(node) {
  focusedNode.value = node
  activeNav.value = 'qa'
}

function onClearFocus() {
  focusedNode.value = null
}

function fitGraph() {
  if (graphRef.value) graphRef.value.fitToScreen()
}

function zoomIn() {
  if (graphRef.value?.zoomBy) graphRef.value.zoomBy(1.18)
}

function zoomOut() {
  if (graphRef.value?.zoomBy) graphRef.value.zoomBy(0.86)
}

async function onCreateNode() {
  const payload = {
    name: form.value.name,
    category: form.value.category,
    difficulty: form.value.difficulty,
    estimated_time: form.value.estimated_time,
    description: form.value.description,
  }
  if (currentCourseId.value) payload.course_id = currentCourseId.value
  try {
    await knowledgeApi.create(payload)
    form.value = { name: '', category: '', difficulty: 1, estimated_time: 0, description: '' }
    await fetchGraph()
    await fetchCategories()
  } catch {
    alert('创建失败')
  }
}

async function onDeleteNode() {
  if (!selectedNode.value || !confirm('确认删除：' + selectedNode.value.name + '？')) return
  try {
    await knowledgeApi.delete(selectedNode.value.id)
    selectedNode.value = null
    await fetchGraph()
    await fetchCategories()
  } catch {
    alert('删除失败')
  }
}

async function onCreateRelation() {
  try {
    await graphApi.createRelation(relSource.value, relTarget.value, relType.value, 1.0)
    await fetchGraph()
  } catch {
    alert('建立关系失败')
  }
}

onMounted(async () => {
  await fetchCourses()
  await fetchClasses()
})
</script>
