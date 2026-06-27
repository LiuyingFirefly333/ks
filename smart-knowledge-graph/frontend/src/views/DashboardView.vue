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

      <div class="topbar-center workspace-title">
        <span>{{ currentNavLabel }}</span>
        <small>{{ currentNavHint }}</small>
      </div>

      <div class="topbar-user">
        <span class="user-role-badge">{{ roleLabel }}</span>
        <span class="user-name">{{ user?.name || '未命名用户' }}</span>
        <button class="ghost-button" @click="switchNav('profile')">个人中心</button>
        <button class="ghost-button" @click="$emit('logout')">退出</button>
      </div>
    </header>

    <div class="app-body">
      <aside class="course-sidebar workspace-sidebar">
        <section class="sidebar-section nav-section">
          <div class="course-sidebar-head">
            <div>
              <span class="sidebar-eyebrow">工作台</span>
              <h2>功能导航</h2>
            </div>
          </div>

          <nav class="sidebar-nav" aria-label="功能导航">
            <button
              v-for="item in navItems"
              :key="item.key"
              class="sidebar-nav-item"
              :class="{ active: activeNav === item.key }"
              :title="item.hint"
              @click="onNavClick(item.key)"
            >
              <span class="sidebar-nav-icon">{{ item.icon }}</span>
              <span>
                <b>{{ item.label }}</b>
                <small>{{ item.hint }}</small>
              </span>
            </button>
          </nav>
        </section>

        <section class="sidebar-section course-section">
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
        </section>

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

      <main class="main-content" :class="{ 'workspace-main': activeNav !== 'graph' }">
        <div v-if="activeNav === 'graph'" class="graph-stage">
          <KnowledgeGraph
            ref="graphRef"
            :nodes="nodes"
            :links="links"
            :highlightedPath="highlightedPath"
            :highlightedPaths="highlightedPaths"
            :searchNodeId="searchNodeId"
            :selectedNodeId="selectedNode?.id"
            :masteryMap="masteryMap"
            :heatmapData="heatmapData"
            :heatmapMode="heatmapMode"
            :editable="canEditGraph"
            :editMode="graphEditMode"
            :selectedLinkKey="selectedLink?.key || ''"
            :selectedNodeIds="batchSelectedIds"
            :relationSourceId="relationSourceId"
            :nodePositions="graphPositions"
            :viewportTransform="currentGraphViewport"
            :initialLayoutMode="currentGraphLayoutMode"
            @select-node="onSelectNode"
            @select-link="onSelectLink"
            @node-position-change="onNodePositionChange"
            @viewport-change="onGraphViewportChange"
            @layout-change="onGraphLayoutChange"
          />
          <div v-if="!currentCourseId" class="graph-empty">
            <div class="empty-kicker">等待课程</div>
            <h2>选择一门课程开始浏览知识图谱</h2>
            <p>课程加载后会展示知识点、前置关系、掌握度与推荐路径。</p>
          </div>
        </div>

        <div v-if="activeNav === 'graph'" class="floating-tools">
          <button
            v-if="canEditGraph"
            :class="{ active: graphEditMode }"
            title="图谱编辑"
            @click="toggleGraphEdit"
          >
            {{ graphEditMode ? '完成' : '编辑' }}
          </button>
          <button title="放大" @click="zoomIn">+</button>
          <button title="缩小" @click="zoomOut">-</button>
        </div>

        <div v-if="activeNav === 'graph'" class="floating-legend">
          <div class="legend-title">图例</div>
          <div class="legend-row"><span class="ldot" style="background:#2563eb"></span>知识点</div>
          <div class="legend-row"><span class="ldot" style="background:#16a34a"></span>熟练</div>
          <div class="legend-row"><span class="ldot" style="background:#f59e0b"></span>一般</div>
          <div class="legend-row"><span class="ldot" style="background:#f97316"></span>薄弱</div>
          <div class="legend-row"><span style="display:inline-block;width:18px;height:2px;background:#ef4444"></span>最短路径</div>
          <div class="legend-row"><span style="display:inline-block;width:18px;height:2px;background:#16a34a"></span>最轻松</div>
          <div class="legend-row"><span style="display:inline-block;width:18px;height:2px;background:#2563eb"></span>最扎实</div>
          <div class="legend-row"><span style="display:inline-block;width:18px;height:0;border-top:2px dashed #94a3b8"></span>相关概念</div>
        </div>

        <section v-if="activeNav !== 'graph'" class="workspace-page">
          <div class="workspace-page-head">
            <div>
              <span class="sidebar-eyebrow">当前功能</span>
              <h2>{{ currentNavLabel }}</h2>
              <p>{{ currentNavHint }}</p>
            </div>
            <button class="soft-button" @click="switchNav('graph')">返回图谱</button>
          </div>

          <div class="workspace-page-body">
            <div v-if="activeNav === 'browse'">
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

            <ChatPanel
              v-if="activeNav === 'qa'"
              :courseId="currentCourseId"
              :focusedNode="focusedNode"
              @locate="onLocateNode"
              @clear-focus="onClearFocus"
            />

            <PathRecommend
              v-if="activeNav === 'path'"
              ref="pathRecommendRef"
              :studentId="user?.id || ''"
              :targetNode="selectedNode"
              :masteredIds="masteredIds"
              @locate="onLocateNode"
              @clear="onClearPath"
              @path-found="onPathFound"
            />

            <ErrorBook v-if="activeNav === 'errors'" :studentId="user?.id" @locate-node="onLocateErrorNode" />

            <TestPaper
              v-if="activeNav === 'paper'"
              :studentId="user?.id"
              :courseId="currentCourseId"
              @locate-node="onLocateErrorNode"
            />

            <ProfileCenter
              v-if="activeNav === 'profile'"
              :user="user"
              :courseId="currentCourseId"
              @updated="$emit('profile-updated', $event)"
              @locate="onLocateNodeId"
            />

            <AdminDashboard v-if="activeNav === 'admin'" @locate="onLocateNodeId" />

            <ClassLearningReport
              v-if="activeNav === 'classReport'"
              :classes="classes"
              :classId="currentClassId"
              :courseId="currentCourseId"
              @locate-node="onLocateNodeId"
            />

            <SubjectiveReview
              v-if="activeNav === 'review'"
              :classes="classes"
              :classId="currentClassId"
              :courseId="currentCourseId"
              @locate-node="onLocateNodeId"
            />

            <ResourceLibrary
              v-if="activeNav === 'resources'"
              :courseId="currentCourseId"
              :nodes="nodes"
            />

            <TeachingResearch
              v-if="activeNav === 'teaching'"
              :courseId="currentCourseId"
              :nodes="nodes"
              @graph-updated="onTeachingGraphUpdated"
            />

            <div v-if="activeNav === 'manage'" class="manage-grid">
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
        </section>
      </main>

      <aside
        v-if="activeNav === 'graph' && graphEditMode && canEditGraph"
        class="slide-panel graph-editor-slide"
      >
        <GraphEditorPanel
          :node="selectedNode"
          :link="selectedLink"
          :nodes="nodes"
          :selectedNodeIds="batchSelectedIds"
          :relationSourceId="relationSourceId"
          :relationDraftType="relationDraftType"
          :relationDraftWeight="relationDraftWeight"
          :batchMode="batchMode"
          @close="toggleGraphEdit(false)"
          @save-node="onSaveNode"
          @delete-node="onDeleteNode"
          @start-relation="onStartRelation"
          @cancel-relation="onCancelRelation"
          @create-relation="onCreateRelationFromEditor"
          @save-link="onSaveLink"
          @delete-link="onDeleteLink"
          @update-relation-draft="onUpdateRelationDraft"
          @toggle-batch="toggleBatchMode"
          @clear-selection="clearBatchSelection"
          @batch-update="onBatchUpdate"
          @batch-delete="onBatchDelete"
          @create-node="onCreateNodeFromEditor"
        />
      </aside>

      <aside
        v-else-if="selectedNode && !['profile', 'admin', 'manage', 'resources', 'teaching', 'review'].includes(activeNav)"
        class="slide-panel"
      >
        <KnowledgePanel
          :node="selectedNode"
          :userId="user?.id || ''"
          :userRole="user?.role || 'student'"
          @close="selectedNode = null; onClearPath()"
          @locate="onLocateNode"
          @show-roadmap="onShowRoadmap"
          @ask-ai="onAskAI"
          @mastery-updated="onManualMasteryUpdated"
        />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { knowledgeApi, graphApi, courseApi, analyticsApi, classroomApi } from '../api/index.js'
import KnowledgeGraph from '../components/KnowledgeGraph.vue'
import KnowledgeSearch from '../components/KnowledgeSearch.vue'
import KnowledgePanel from '../components/KnowledgePanel.vue'
import GraphEditorPanel from '../components/GraphEditorPanel.vue'
import PathRecommend from '../components/PathRecommend.vue'
import ChatPanel from '../components/ChatPanel.vue'
import ErrorBook from '../components/ErrorBook.vue'
import TestPaper from '../components/TestPaper.vue'
import AdminDashboard from '../components/AdminDashboard.vue'
import ProfileCenter from '../components/ProfileCenter.vue'
import ResourceLibrary from '../components/ResourceLibrary.vue'
import ClassLearningReport from '../components/ClassLearningReport.vue'
import TeachingResearch from '../components/TeachingResearch.vue'
import SubjectiveReview from '../components/SubjectiveReview.vue'

const props = defineProps({ user: { type: Object, default: null } })
defineEmits(['logout', 'profile-updated'])

const roleLabel = computed(() => ({ student: '学生', teacher: '教师', admin: '管理员' }[props.user?.role] || '学生'))
const canEditGraph = computed(() => props.user?.role === 'teacher' || props.user?.role === 'admin')

const NAV_DEFS = {
  graph: { key: 'graph', icon: 'KG', label: '知识图谱', hint: '全局关系视图' },
  browse: { key: 'browse', icon: 'BR', label: '知识浏览', hint: '搜索与筛选节点' },
  qa: { key: 'qa', icon: 'AI', label: 'AI 问答', hint: '结合图谱上下文答疑' },
  path: { key: 'path', icon: 'PT', label: '学习路径', hint: '推荐补习路线' },
  errors: { key: 'errors', icon: 'ER', label: '错题本', hint: '错题溯源分析' },
  paper: { key: 'paper', icon: 'EX', label: '智能组卷', hint: '薄弱点专项训练' },
  resources: { key: 'resources', icon: 'RS', label: '资源库', hint: '资源管理与批量挂载' },
  teaching: { key: 'teaching', icon: 'TR', label: '备课教研', hint: '课件上传、抽取建图与命题统计' },
  classReport: { key: 'classReport', icon: 'CR', label: '班级报告', hint: '错题统计与精准教学' },
  review: { key: 'review', icon: 'RV', label: '主观题批阅', hint: '批阅待处理主观题' },
  manage: { key: 'manage', icon: 'MG', label: '知识管理', hint: '维护节点与关系' },
  admin: { key: 'admin', icon: 'AD', label: '数据看板', hint: '平台与知识库运营' },
  profile: { key: 'profile', icon: 'ME', label: '个人中心', hint: '资料编辑与学习概览' },
}

const ROLE_NAV_KEYS = {
  student: ['graph', 'browse', 'qa', 'path', 'errors', 'paper'],
  teacher: ['graph', 'browse', 'qa', 'teaching', 'classReport', 'review', 'resources', 'manage'],
  admin: ['graph', 'browse', 'resources', 'manage', 'admin'],
}

const navItems = computed(() => {
  const role = props.user?.role || 'student'
  return (ROLE_NAV_KEYS[role] || ROLE_NAV_KEYS.student).map(key => NAV_DEFS[key]).filter(Boolean)
})

const currentNav = computed(() => NAV_DEFS[activeNav.value] || NAV_DEFS.graph)
const currentNavLabel = computed(() => currentNav.value.label)
const currentNavHint = computed(() => currentNav.value.hint)

const graphRef = ref(null)
const pathRecommendRef = ref(null)
const activeNav = ref('graph')
const nodes = ref([])
const links = ref([])
const categories = ref([])
const selectedCategory = ref('')
const selectedNode = ref(null)
const selectedLink = ref(null)
const highlightedPath = ref([])
const highlightedPaths = ref([])
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
const graphEditMode = ref(false)
const graphPositions = ref({})
const graphViewports = ref({})
const graphLayoutModes = ref({})
const relationSourceId = ref('')
const relationDraftType = ref('PREREQUISITE')
const relationDraftWeight = ref(1)
const batchMode = ref(false)
const batchSelectedIds = ref([])
const form = ref({ name: '', category: '', difficulty: 1, estimated_time: 0, description: '' })
const relSource = ref('')
const relTarget = ref('')
const relType = ref('PREREQUISITE')
const currentGraphViewport = computed(() => graphViewports.value[currentCourseId.value || 'global'] || null)
const currentGraphLayoutMode = computed(() => graphLayoutModes.value[currentCourseId.value || 'global'] || 'dagre')

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

function normalizeId(value) {
  return typeof value === 'object' ? value?.id || '' : value || ''
}

function relationKey(link) {
  if (!link) return ''
  return `${normalizeId(link.source)}->${normalizeId(link.target)}:${link.type || 'RELATED_TO'}`
}

function positionStorageKey() {
  return `kg:positions:${currentCourseId.value || 'global'}`
}

function loadGraphPositions() {
  try {
    graphPositions.value = JSON.parse(localStorage.getItem(positionStorageKey()) || '{}')
  } catch {
    graphPositions.value = {}
  }
}

function saveGraphPositions() {
  localStorage.setItem(positionStorageKey(), JSON.stringify(graphPositions.value))
}

function viewportStorageKey() {
  return currentCourseId.value || 'global'
}

function recordGraphViewport() {
  const viewport = graphRef.value?.getViewport?.()
  if (viewport) onGraphViewportChange(viewport)
}

function onGraphViewportChange(viewport) {
  if (!viewport) return
  const x = Number(viewport.x)
  const y = Number(viewport.y)
  const k = Number(viewport.k)
  if (![x, y, k].every(Number.isFinite)) return
  const key = viewportStorageKey()
  if (viewport.layoutMode) {
    graphLayoutModes.value = {
      ...graphLayoutModes.value,
      [key]: viewport.layoutMode === 'force' ? 'force' : 'dagre',
    }
  }
  graphViewports.value = {
    ...graphViewports.value,
    [key]: {
      x,
      y,
      k,
      layoutMode: viewport.layoutMode,
    },
  }
}

function onGraphLayoutChange(mode) {
  const key = viewportStorageKey()
  graphLayoutModes.value = { ...graphLayoutModes.value, [key]: mode === 'force' ? 'force' : 'dagre' }
  const { [key]: _removed, ...rest } = graphViewports.value
  graphViewports.value = rest
}

function toggleGraphEdit(force) {
  if (!canEditGraph.value) return
  graphEditMode.value = typeof force === 'boolean' ? force : !graphEditMode.value
  activeNav.value = 'graph'
  if (!graphEditMode.value) {
    selectedLink.value = null
    relationSourceId.value = ''
    batchMode.value = false
    batchSelectedIds.value = []
  }
}

function onNodePositionChange(position) {
  graphPositions.value = {
    ...graphPositions.value,
    [position.id]: {
      x: Math.round(position.x),
      y: Math.round(position.y),
    },
  }
  saveGraphPositions()
}

function isNavAllowed(key) {
  return key === 'profile' || navItems.value.some(item => item.key === key)
}

function switchNav(key) {
  const nextKey = isNavAllowed(key) ? key : 'graph'
  if (activeNav.value === 'graph' && nextKey !== 'graph') recordGraphViewport()
  activeNav.value = nextKey
}

function onNavClick(key) {
  switchNav(activeNav.value === key && key !== 'graph' ? 'graph' : key)
}

async function selectCourse(courseId) {
  if (currentCourseId.value === courseId) return
  recordGraphViewport()
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
  selectedLink.value = null
  relationSourceId.value = ''
  batchSelectedIds.value = []
  highlightedPath.value = []
  highlightedPaths.value = []
  selectedCategory.value = ''
  loadGraphPositions()
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

async function onSelectNode(node, meta = {}) {
  if (graphEditMode.value && relationSourceId.value && relationSourceId.value !== node.id) {
    const sourceId = relationSourceId.value
    const type = relationDraftType.value || 'PREREQUISITE'
    const weight = Number(relationDraftWeight.value || 1)
    const created = await createRelationByIds(sourceId, node.id, type, weight)
    if (!created) return
    relationSourceId.value = ''
    selectedLink.value = {
      source: sourceId,
      target: node.id,
      type,
      weight,
      key: `${sourceId}->${node.id}:${type}`,
    }
    return
  }

  if (graphEditMode.value && (batchMode.value || meta.additive)) {
    const set = new Set(batchSelectedIds.value)
    if (set.has(node.id)) set.delete(node.id)
    else set.add(node.id)
    batchSelectedIds.value = [...set]
  }

  selectedNode.value = node
  selectedLink.value = null
  searchNodeId.value = null
}

function onSelectLink(link) {
  if (!canEditGraph.value) return
  graphEditMode.value = true
  selectedLink.value = { ...link, key: link.key || relationKey(link) }
  selectedNode.value = null
  searchNodeId.value = null
}

async function onLocateNode(node) {
  selectedNode.value = node
  selectedLink.value = null
  searchNodeId.value = node.id
  activeNav.value = 'graph'
  await nextTick()
  if (graphRef.value) graphRef.value.locateNode(node.id)
}

function onLocateNodeId(nodeId) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (node) onLocateNode(node)
}

function onLocateErrorNode(nodeId) {
  onLocateNodeId(nodeId)
}

function onPathFound(pathNodes, _totalTime, _type, pathGroups = []) {
  highlightedPath.value = pathNodes.map(n => n.id)
  highlightedPaths.value = pathGroups.map(group => ({
    ...group,
    nodes: (group.path || []).map(node => node.id),
  }))
}

async function onShowRoadmap(targetId) {
  if (!isNavAllowed('path')) return
  switchNav('path')
  await nextTick()
  if (pathRecommendRef.value) pathRecommendRef.value.fetchPath(targetId)
}

function onClearPath() {
  highlightedPath.value = []
  highlightedPaths.value = []
}

function onAskAI(node) {
  if (!isNavAllowed('qa')) return
  focusedNode.value = node
  switchNav('qa')
}

function onClearFocus() {
  focusedNode.value = null
}

async function onTeachingGraphUpdated() {
  await fetchGraph()
  await fetchCategories()
}

async function onManualMasteryUpdated(payload) {
  const nodeId = payload?.node_id
  const score = Number(payload?.score || 0)
  if (nodeId) {
    const level = score >= 85 ? 'proficient' : score >= 60 ? 'fair' : score > 0 ? 'weak' : 'unlearned'
    masteryMap.value = {
      ...masteryMap.value,
      [nodeId]: { ...(masteryMap.value[nodeId] || {}), score, level, manual_score: score },
    }
    nodes.value = nodes.value.map(node => (
      node.id === nodeId
        ? { ...node, mastery_score: score, mastery_level: level, manual_score: score }
        : node
    ))
    if (selectedNode.value?.id === nodeId) {
      selectedNode.value = { ...selectedNode.value, mastery_score: score, mastery_level: level, manual_score: score }
    }
  }
  await fetchMastery()
  await fetchGraph()
}

function zoomIn() {
  if (graphRef.value?.zoomBy) graphRef.value.zoomBy(1.18)
}

function zoomOut() {
  if (graphRef.value?.zoomBy) graphRef.value.zoomBy(0.86)
}

async function onSaveNode(node, payload) {
  if (!node?.id) return
  try {
    const updated = await knowledgeApi.update(node.id, payload)
    nodes.value = nodes.value.map(n => n.id === updated.id ? updated : n)
    selectedNode.value = updated
    await fetchCategories()
  } catch {
    alert('保存知识点失败')
  }
}

function onStartRelation(nodeId) {
  relationSourceId.value = nodeId
  selectedLink.value = null
  activeNav.value = 'graph'
}

function onCancelRelation() {
  relationSourceId.value = ''
}

function onUpdateRelationDraft(payload) {
  relationDraftType.value = payload.type || 'PREREQUISITE'
  relationDraftWeight.value = Number(payload.weight || 1)
}

async function createRelationByIds(source, target, type = 'PREREQUISITE', weight = 1) {
  try {
    await graphApi.createRelation(source, target, type, weight)
    await fetchGraph()
    return true
  } catch {
    alert('建立关系失败')
    return false
  }
}

async function onCreateRelationFromEditor(payload) {
  const created = await createRelationByIds(payload.source, payload.target, payload.type, payload.weight)
  if (!created) return
  relationSourceId.value = ''
  selectedLink.value = {
    source: payload.source,
    target: payload.target,
    type: payload.type,
    weight: payload.weight,
    key: `${payload.source}->${payload.target}:${payload.type}`,
  }
}

async function onSaveLink(link, payload) {
  if (!link) return
  try {
    const updated = await graphApi.updateRelation(
      normalizeId(link.source),
      normalizeId(link.target),
      link.type,
      payload.source,
      payload.target,
      payload.type,
      payload.weight,
    )
    await fetchGraph()
    selectedLink.value = { ...updated, key: relationKey(updated) }
  } catch {
    alert('保存关系失败')
  }
}

async function onDeleteLink(link) {
  if (!link || !confirm('确认删除该关系？')) return
  try {
    await graphApi.deleteRelation(normalizeId(link.source), normalizeId(link.target), link.type)
    selectedLink.value = null
    await fetchGraph()
  } catch {
    alert('删除关系失败')
  }
}

function toggleBatchMode() {
  batchMode.value = !batchMode.value
}

function clearBatchSelection() {
  batchSelectedIds.value = []
}

async function onBatchUpdate(payload) {
  if (!batchSelectedIds.value.length || !Object.keys(payload).length) return
  try {
    await Promise.all(batchSelectedIds.value.map(id => knowledgeApi.update(id, payload)))
    await fetchGraph()
    await fetchCategories()
  } catch {
    alert('批量更新失败')
  }
}

async function onBatchDelete() {
  if (!batchSelectedIds.value.length || !confirm('确认批量删除选中的知识点？')) return
  try {
    await Promise.all(batchSelectedIds.value.map(id => knowledgeApi.delete(id)))
    if (selectedNode.value && batchSelectedIds.value.includes(selectedNode.value.id)) selectedNode.value = null
    batchSelectedIds.value = []
    await fetchGraph()
    await fetchCategories()
  } catch {
    alert('批量删除失败')
  }
}

async function onCreateNodeFromEditor(payload) {
  if (currentCourseId.value) payload.course_id = currentCourseId.value
  try {
    const created = await knowledgeApi.create(payload)
    selectedNode.value = created
    selectedLink.value = null
    await fetchGraph()
    await fetchCategories()
  } catch {
    alert('创建知识点失败')
  }
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

async function onDeleteNode(node = selectedNode.value) {
  if (!node || !confirm('确认删除：' + node.name + '？')) return
  try {
    await knowledgeApi.delete(node.id)
    delete graphPositions.value[node.id]
    saveGraphPositions()
    selectedNode.value = null
    selectedLink.value = null
    batchSelectedIds.value = batchSelectedIds.value.filter(id => id !== node.id)
    await fetchGraph()
    await fetchCategories()
  } catch {
    alert('删除失败')
  }
}

async function onCreateRelation() {
  try {
    await graphApi.createRelation(relSource.value, relTarget.value, relType.value, 1.0)
    selectedLink.value = {
      source: relSource.value,
      target: relTarget.value,
      type: relType.value,
      weight: 1,
      key: `${relSource.value}->${relTarget.value}:${relType.value}`,
    }
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
