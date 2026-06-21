<template>
  <div class="app-layout">
    <!-- 左侧面板 -->
    <div class="sidebar">
      <div class="sidebar-header">
        <h1>知识图谱</h1>
        <div class="header-meta">
          <span class="badge">{{ nodes.length }} 节点</span>
          <span class="user-info" :title="user?.email">
            <span class="avatar" :class="{ teacher: isTeacher }">{{ user?.name?.charAt(0) }}</span>
            {{ user?.name }}
          </span>
          <button class="btn-logout" @click="$emit('logout')" title="退出登录">&#10005;</button>
        </div>
      </div>

      <!-- 课程选择器 -->
      <div class="course-selector">
        <select v-model="currentCourseId" @change="onCourseChange">
          <option value="">-- 选择课程 --</option>
          <option v-for="c in courses" :key="c.id" :value="c.id">
            {{ c.name }} ({{ c.node_count || 0 }})
          </option>
        </select>
      </div>

      <div class="sidebar-tabs">
        <button :class="{ active: tab === 'browse' }" @click="tab = 'browse'">浏览</button>
        <button :class="{ active: tab === 'path' }" @click="tab = 'path'">学习路径</button>
        <button :class="{ active: tab === 'manage' }" @click="tab = 'manage'">管理</button>
      </div>

      <div class="sidebar-content">
        <!-- 浏览标签 -->
        <div v-show="tab === 'browse'">
          <KnowledgeSearch v-if="currentCourseId" :courseId="currentCourseId" @locate="onLocateNode" />
          <div class="cat-selector" v-if="currentCourseId">
            <button :class="{ active: !selectedCategory }" @click="selectedCategory = ''; fetchGraph()">全部</button>
            <button
              v-for="cat in categories" :key="cat"
              :class="{ active: selectedCategory === cat }"
              @click="selectedCategory = cat; fetchGraph()"
            >{{ cat.split('-').pop() }}</button>
          </div>
          <div v-if="!currentCourseId" class="empty-state">请先选择一门课程</div>
          <div class="node-list" v-else>
            <div
              v-for="n in nodes" :key="n.id"
              class="node-item"
              :style="{ borderLeft: '3px solid ' + getColor(n.category) }"
              @click="onSelectNode(n)"
            >
              <span>{{ n.name }}</span>
              <span class="cat-tag">{{ n.category.split('-').pop() }}</span>
            </div>
          </div>
        </div>

        <!-- 路径标签 -->
        <div v-show="tab === 'path'">
          <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px">
            点击图谱上的知识点查看推荐路径
          </p>
          <PathRecommend
            ref="pathRecommendRef"
            :targetNode="selectedNode"
            :masteredIds="masteredIds"
        :studentId="user?.id"
            @locate="onLocateNode"
            @clear="onClearPath"
            @path-found="onPathFound"
          />
        </div>

        <!-- 管理标签 -->
        <div v-show="tab === 'manage'">
          <div class="manage-form">
            <div class="row">
              <label>知识点名称</label>
              <input v-model="form.name" placeholder="如：导数的概念" />
            </div>
            <div class="row">
              <label>分类</label>
              <input v-model="form.category" placeholder="如：高等数学-导数" />
            </div>
            <div class="row">
              <label>难度 (1-5)</label>
              <input v-model.number="form.difficulty" type="number" min="1" max="5" />
            </div>
            <div class="row">
              <label>描述</label>
              <textarea v-model="form.description" rows="2"></textarea>
            </div>
            <div class="form-actions">
              <button @click="onCreateNode" :disabled="!form.name">创建</button>
              <button v-if="selectedNode" class="danger" @click="onDeleteNode">删除选中</button>
            </div>
          </div>
          <div style="margin-top: 16px">
            <h4 style="font-size: 13px; margin-bottom: 6px">建立关系</h4>
            <div class="manage-form">
              <div class="row">
                <label>源知识点</label>
                <select v-model="relSource">
                  <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
                </select>
              </div>
              <div class="row">
                <label>目标知识点</label>
                <select v-model="relTarget">
                  <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
                </select>
              </div>
              <div class="row">
                <label>关系类型</label>
                <select v-model="relType">
                  <option value="PREREQUISITE">前置知识 (&rarr;)</option>
                  <option value="RELATED_TO">相关概念 (&harr;)</option>
                </select>
              </div>
              <button @click="onCreateRelation" :disabled="!relSource || !relTarget">建立关系</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 图谱主区域 -->
    <div class="main-area">
      <div class="graph-toolbar">
        <button title="适应屏幕" @click="fitGraph">&#8862;</button>
        <button title="放大" @click="zoomIn">+</button>
        <button title="缩小" @click="zoomOut">-</button>
      </div>

      <KnowledgeGraph
        ref="graphRef"
        :nodes="nodes"
        :links="links"
        :highlightedPath="highlightedPath"
        :searchNodeId="searchNodeId"
        :selectedNodeId="selectedNode?.id"
        @select-node="onSelectNode"
      />

      <!-- 图例 -->
      <div class="graph-legend">
        <div class="graph-legend-item"><span class="dot" style="background:#6366f1"></span> 基础</div>
        <div class="graph-legend-item"><span class="dot" style="background:#22c55e"></span> 极限</div>
        <div class="graph-legend-item"><span class="dot" style="background:#f59e0b"></span> 导数</div>
        <div class="graph-legend-item"><span class="dot" style="background:#3b82f6"></span> 积分</div>
        <div class="graph-legend-item"><span class="dot" style="background:#ef4444"></span> 微分方程</div>
        <div class="graph-legend-item" style="margin-top:4px">
          <span style="display:inline-block;width:20px;height:2px;background:#ef4444"></span> 推荐路径
        </div>
        <div class="graph-legend-item">
          <span style="display:inline-block;width:20px;height:0;border-top:2px dashed #475569"></span> 相关概念
        </div>
      </div>

      <!-- 详情面板 -->
      <KnowledgePanel
        v-if="selectedNode"
        :node="selectedNode"
        @close="selectedNode = null; onClearPath()"
        @locate="onLocateNode"
        @show-roadmap="onShowRoadmap"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { knowledgeApi, graphApi, courseApi } from '../api/index.js'
import KnowledgeGraph from '../components/KnowledgeGraph.vue'
import KnowledgeSearch from '../components/KnowledgeSearch.vue'
import KnowledgePanel from '../components/KnowledgePanel.vue'
import PathRecommend from '../components/PathRecommend.vue'

const props = defineProps({
  user: { type: Object, default: null },
})

const emit = defineEmits(['logout'])

const isTeacher = computed(() => props.user?.role === 'teacher')

const graphRef = ref(null)
const pathRecommendRef = ref(null)

const tab = ref('browse')
const nodes = ref([])
const links = ref([])
const categories = ref([])
const selectedCategory = ref('')
const selectedNode = ref(null)
const highlightedPath = ref([])
const searchNodeId = ref(null)
const courses = ref([])
const currentCourseId = ref('')
const masteredIds = ref([])

const form = ref({ name: '', category: '', difficulty: 1, description: '' })
const relSource = ref('')
const relTarget = ref('')
const relType = ref('PREREQUISITE')
const courseForm = ref({ name: '', description: '' })

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

async function fetchGraph() {
  if (!currentCourseId.value) {
    nodes.value = []
    links.value = []
    return
  }
  try {
    const data = await graphApi.getGraph(
      selectedCategory.value || undefined,
      currentCourseId.value,
      props.user?.id
    )
    nodes.value = data.nodes || []
    links.value = data.links || []
    nodes.value.forEach(n => {
      n._mastery = data.nodes.find(x => x.id === n.id)?.mastery_score || 0
    })
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

function onCourseChange() {
  selectedNode.value = null
  highlightedPath.value = []
  fetchGraph()
  fetchCategories()
}

function onSelectNode(node) {
  selectedNode.value = node
  searchNodeId.value = null
}

function onLocateNode(node) {
  selectedNode.value = node
  searchNodeId.value = node.id
  if (graphRef.value) {
    graphRef.value.locateNode(node.id)
  }
}

function onPathFound(pathNodes) {
  highlightedPath.value = pathNodes.map(n => n.id)
}

function onShowRoadmap(targetId) {
  tab.value = 'path'
  if (pathRecommendRef.value) {
    pathRecommendRef.value.fetchPath(targetId)
  }
}

function onClearPath() {
  highlightedPath.value = []
}

function fitGraph() {
  if (graphRef.value) graphRef.value.fitToScreen()
}

function zoomIn() {}
function zoomOut() {}

async function onCreateNode() {
  const payload = { ...form.value }
  if (currentCourseId.value) {
    payload.course_id = currentCourseId.value
  }
  try {
    await knowledgeApi.create(payload)
    form.value = { name: '', category: '', difficulty: 1, description: '' }
    await fetchGraph()
    await fetchCategories()
  } catch (e) {
    alert('创建失败: ' + (e.response?.data?.error || e.message))
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

async function onCreateCourse() {
  try {
    await courseApi.create({ ...courseForm.value }, props.user?.id)
    courseForm.value = { name: '', description: '' }
    await fetchCourses()
  } catch (e) {
    alert('创建课程失败: ' + (e.response?.data?.error || e.message))
  }
}

onMounted(async () => {
  await fetchCourses()
})
</script>
