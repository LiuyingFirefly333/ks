<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-brand">
        <span class="brand-icon">KG</span>
        <span class="brand-text">知识图谱学习平台</span>
      </div>

      <div class="topbar-center">
        <select v-model="currentCourseId" @change="onCourseChange" class="topbar-course">
          <option value="">全部课程</option>
          <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>

        <select
          v-if="user?.role === 'teacher'"
          v-model="currentClassId"
          @change="onClassChange"
          class="topbar-course"
        >
          <option value="">全部班级</option>
          <option v-for="c in classes" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>

        <button
          v-if="user?.role === 'teacher'"
          class="topbar-heatmap-btn"
          :class="{ active: heatmapMode }"
          @click="toggleHeatmap"
        >
          {{ heatmapMode ? '关闭热力图' : '班级热力图' }}
        </button>
      </div>

      <div class="topbar-user">
        <span class="user-role-badge">{{ roleLabel }}</span>
        <span class="user-name">{{ user?.name }}</span>
        <button class="topbar-logout" @click="$emit('logout')">退出</button>
      </div>
    </header>

    <div class="app-body">
      <nav class="sidenav">
        <button
          v-for="item in navItems"
          :key="item.key"
          class="sidenav-item"
          :class="{ active: activeNav === item.key }"
          :title="item.label"
          @click="onNavClick(item.key)"
        >
          <span class="sidenav-icon">{{ item.icon }}</span>
          <span class="sidenav-label">{{ item.label }}</span>
        </button>
      </nav>

      <main class="main-content">
        <div class="graph-area">
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
        </div>

        <div class="floating-tools">
          <button title="适应屏幕" @click="fitGraph">Fit</button>
          <button title="放大" @click="zoomIn">+</button>
          <button title="缩小" @click="zoomOut">-</button>
        </div>

        <div class="floating-legend">
          <div class="legend-row"><span class="ldot" style="background:#6366f1"></span>基础</div>
          <div class="legend-row"><span class="ldot" style="background:#22c55e"></span>极限</div>
          <div class="legend-row"><span class="ldot" style="background:#f59e0b"></span>导数</div>
          <div class="legend-row"><span class="ldot" style="background:#3b82f6"></span>积分</div>
          <div class="legend-row"><span class="ldot" style="background:#ef4444"></span>微分方程</div>
          <div class="legend-row"><span style="display:inline-block;width:16px;height:2px;background:#ef4444"></span>推荐路径</div>
          <div class="legend-row"><span style="display:inline-block;width:16px;height:0;border-top:2px dashed #475569"></span>相关概念</div>
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
        <span>{{ currentNavLabel }}</span>
        <span class="drawer-close">关闭</span>
      </div>

      <div class="drawer-body">
        <div v-if="activeNav === 'browse'" class="drawer-scroll">
          <KnowledgeSearch v-if="currentCourseId" :courseId="currentCourseId" @locate="onLocateNode" />
          <div class="cat-selector" v-if="currentCourseId">
            <button :class="{ active: !selectedCategory }" @click="selectedCategory = ''; fetchGraph()">全部</button>
            <button
              v-for="cat in categories"
              :key="cat"
              :class="{ active: selectedCategory === cat }"
              @click="selectedCategory = cat; fetchGraph()"
            >
              {{ cat.split('-').pop() }}
            </button>
          </div>
          <div v-if="!currentCourseId" class="empty-state">请先选择一门课程</div>
          <div class="node-list" v-else>
            <div v-for="n in nodes" :key="n.id" class="node-card" @click="onSelectNode(n)">
              <div class="node-card-left" :style="{ borderLeftColor: getColor(n.category) }">
                <span class="node-card-name">{{ n.name }}</span>
                <span class="node-card-cat">{{ n.category.split('-').pop() }}</span>
              </div>
              <span v-if="n.estimated_time" class="node-card-time">{{ n.estimated_time }} 分钟</span>
            </div>
          </div>
        </div>

        <div v-if="activeNav === 'qa'" class="drawer-scroll">
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

        <div v-if="activeNav === 'manage'" class="drawer-scroll">
          <div class="manage-form">
            <div class="form-row">
              <label>知识点名称</label>
              <input v-model="form.name" placeholder="如：导数的概念" />
            </div>
            <div class="form-row">
              <label>分类</label>
              <input v-model="form.category" placeholder="如：高等数学-导数" />
            </div>
            <div class="form-row">
              <label>难度 (1-5)</label>
              <input v-model.number="form.difficulty" type="number" min="1" max="5" />
            </div>
            <div class="form-row">
              <label>预计时长（分钟）</label>
              <input v-model.number="form.estimated_time" type="number" min="0" placeholder="如：45" />
            </div>
            <div class="form-row">
              <label>描述</label>
              <textarea v-model="form.description" rows="2"></textarea>
            </div>
            <div class="form-actions">
              <button @click="onCreateNode" :disabled="!form.name">创建知识点</button>
              <button v-if="selectedNode" class="danger" @click="onDeleteNode">删除选中</button>
            </div>
          </div>

          <div class="manage-form" style="margin-top:16px">
            <h4>建立关系</h4>
            <div class="form-row">
              <label>源知识点</label>
              <select v-model="relSource">
                <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
              </select>
            </div>
            <div class="form-row">
              <label>目标知识点</label>
              <select v-model="relTarget">
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

const props = defineProps({ user: { type: Object, default: null } })
defineEmits(['logout'])

const roleLabel = computed(() => ({ student: '学生', teacher: '教师', admin: '管理员' }[props.user?.role] || '学生'))

const navItems = computed(() => {
  const items = [
    { key: 'graph', icon: '图', label: '知识图谱' },
    { key: 'browse', icon: '览', label: '浏览节点' },
    { key: 'qa', icon: '问', label: 'AI 问答' },
    { key: 'path', icon: '路', label: '学习路径' },
    { key: 'errors', icon: '错', label: '错题本' },
    { key: 'paper', icon: '卷', label: '智能组卷' },
  ]
  if (props.user?.role === 'teacher' || props.user?.role === 'admin') {
    items.push({ key: 'manage', icon: '管', label: '知识管理' })
  }
  return items
})

const currentNavLabel = computed(() => navItems.value.find(n => n.key === activeNav.value)?.label || '')

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

function getColor(cat) {
  const map = {
    '高等数学-基础': '#6366f1',
    '高等数学-极限': '#22c55e',
    '高等数学-导数': '#f59e0b',
    '高等数学-积分': '#3b82f6',
    '高等数学-微分方程': '#ef4444',
  }
  return map[cat] || '#8b5cf6'
}

function onNavClick(key) {
  activeNav.value = activeNav.value === key && key !== 'graph' ? 'graph' : key
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
    console.error('加载图谱失败', e)
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
  } catch {
    masteryMap.value = {}
  }
}

async function onCourseChange() {
  selectedNode.value = null
  highlightedPath.value = []
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

function onLocateErrorNode(nodeId) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (node) onSelectNode(node)
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

function zoomIn() {}
function zoomOut() {}

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
  if (!selectedNode.value || !confirm('确认删除：' + selectedNode.value.name + '?')) return
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
