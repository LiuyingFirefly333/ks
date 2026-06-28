<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-brand">
        <span class="brand-mark" aria-hidden="true">
          <svg class="brand-logo-icon" viewBox="0 0 24 24">
            <circle cx="6" cy="8" r="2.4" />
            <circle cx="18" cy="7" r="2.4" />
            <circle cx="12" cy="18" r="2.6" />
            <path d="M8.3 7.8l7.4-.6" />
            <path d="M7.3 10l3.8 5.8" />
            <path d="M16.8 9.2l-3.6 6.5" />
          </svg>
        </span>
        <div>
          <div class="brand-text">智能知识图谱学习系统</div>
          <div class="brand-subtitle">Knowledge Graph Learning Workspace</div>
        </div>
      </div>

      <div class="topbar-user">
        <span class="user-role-badge">{{ roleLabel }}</span>
        <span class="user-name">{{ displayName }}</span>
        <button class="avatar-button" :title="'个人中心：' + displayName" aria-label="打开个人中心" @click="switchNav('profile')">
          <img v-if="user?.avatar_url" :src="user.avatar_url" :alt="displayName + '的头像'" />
          <span v-else class="avatar-fallback">{{ userInitials }}</span>
        </button>
        <button class="logout-button" @click="$emit('logout')">退出</button>
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
            <div v-for="group in navGroups" :key="group.title" class="sidebar-nav-group">
              <div class="sidebar-nav-group-title">{{ group.title }}</div>
              <button
                v-for="item in group.items"
                :key="item.key"
                class="sidebar-nav-item"
                :class="{ active: activeNav === item.key }"
                :title="item.hint"
                @click="onNavClick(item.key)"
              >
                <span class="sidebar-nav-icon" v-html="item.icon"></span>
                <span>
                  <b>{{ item.label }}</b>
                  <small>{{ item.hint }}</small>
                </span>
              </button>
            </div>
          </nav>
        </section>

        <section v-if="showNextAction" class="sidebar-section next-action-section">
          <button
            type="button"
            class="next-action-close"
            aria-label="关闭下一步建议"
            title="关闭"
            @click="showNextAction = false"
          >
            ×
          </button>
          <div class="course-sidebar-head">
            <div>
              <span class="sidebar-eyebrow">下一步</span>
              <h2>{{ primaryAction.title }}</h2>
            </div>
          </div>
          <p>{{ primaryAction.text }}</p>
          <button class="soft-button full-width" @click="switchNav(primaryAction.nav)">
            {{ primaryAction.cta }}
          </button>
        </section>

      </aside>

      <main class="main-content" :class="{ 'workspace-main': activeNav !== 'graph' }">
        <div v-if="activeNav === 'graph'" class="graph-stage">
          <div class="graph-course-switcher" :class="{ 'has-class-view': user?.role === 'teacher' }">
            <div class="top-course-switcher">
              <span class="top-course-kicker">当前课程</span>
              <span class="top-course-select-wrap">
                <button
                  type="button"
                  class="top-course-trigger"
                  :disabled="!courses.length"
                  aria-label="切换课程"
                  aria-haspopup="listbox"
                  :aria-expanded="courseMenuOpen"
                  @click="courseMenuOpen = !courseMenuOpen; classMenuOpen = false"
                >
                  <span>{{ currentCourseName }}</span>
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </button>
                <div v-if="courseMenuOpen" class="top-course-menu" role="listbox">
                  <button
                    v-for="course in courses"
                    :key="course.id"
                    type="button"
                    class="top-course-option"
                    :class="{ active: currentCourseId === course.id }"
                    role="option"
                    :aria-selected="currentCourseId === course.id"
                    @click="chooseCourse(course.id)"
                  >
                    <span>{{ course.name }}</span>
                    <b v-if="currentCourseId === course.id">当前</b>
                  </button>
                </div>
              </span>
            </div>

            <div v-if="user?.role === 'teacher'" class="top-course-switcher top-class-switcher">
              <span class="top-course-kicker">班级视图</span>
              <span class="top-course-select-wrap">
                <button
                  type="button"
                  class="top-course-trigger"
                  aria-label="切换班级视图"
                  aria-haspopup="listbox"
                  :aria-expanded="classMenuOpen"
                  @click="classMenuOpen = !classMenuOpen; courseMenuOpen = false"
                >
                  <span>{{ currentClassName }}</span>
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </button>
                <div v-if="classMenuOpen" class="top-course-menu" role="listbox">
                  <button
                    type="button"
                    class="top-course-option"
                    :class="{ active: !currentClassId }"
                    role="option"
                    :aria-selected="!currentClassId"
                    @click="chooseClass('')"
                  >
                    <span>全部班级</span>
                    <b v-if="!currentClassId">当前</b>
                  </button>
                  <button
                    v-for="c in classes"
                    :key="c.id"
                    type="button"
                    class="top-course-option"
                    :class="{ active: currentClassId === c.id }"
                    role="option"
                    :aria-selected="currentClassId === c.id"
                    @click="chooseClass(c.id)"
                  >
                    <span>{{ c.name }}</span>
                    <b v-if="currentClassId === c.id">当前</b>
                  </button>
                </div>
              </span>
            </div>
          </div>
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

        <div v-if="activeNav === 'graph'" class="graph-action-tools">
          <button
            v-if="canEditGraph"
            :class="{ active: graphEditMode }"
            title="图谱编辑"
            @click="toggleGraphEdit"
          >
            {{ graphEditMode ? '完成' : '编辑' }}
          </button>
          <div class="graph-export-dropdown">
            <button
              class="graph-export-button"
              :class="{ active: exportMenuOpen }"
              title="导出图谱"
              @click="exportMenuOpen = !exportMenuOpen"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 3v11" />
                <path d="M7 10l5 5 5-5" />
                <path d="M5 21h14" />
              </svg>
              导出图谱
            </button>
            <div v-if="exportMenuOpen" class="graph-export-menu">
              <button @click="exportGraph('svg')">SVG 图片</button>
              <button @click="exportGraph('json')">JSON 数据</button>
              <button @click="exportGraph('csv')">CSV 表格</button>
            </div>
          </div>
          <label
            v-if="user?.role === 'teacher'"
            class="graph-heatmap-switch"
            :class="{ active: heatmapMode }"
          >
            <span>班级热力图</span>
            <input
              type="checkbox"
              :checked="heatmapMode"
              aria-label="切换班级热力图"
              @change="toggleHeatmap"
            />
            <i aria-hidden="true"></i>
          </label>
        </div>

        <div v-if="activeNav === 'graph'" class="graph-zoom-tools">
          <button title="适应画布" aria-label="适应画布" @click="fitGraph">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 3H3v5" />
              <path d="M16 3h5v5" />
              <path d="M8 21H3v-5" />
              <path d="M16 21h5v-5" />
              <path d="M3 3l6 6" />
              <path d="M21 3l-6 6" />
              <path d="M3 21l6-6" />
              <path d="M21 21l-6-6" />
            </svg>
          </button>
          <button title="放大" aria-label="放大图谱" @click="zoomIn">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="M21 21l-4.3-4.3" />
              <path d="M11 8v6" />
              <path d="M8 11h6" />
            </svg>
          </button>
          <button title="缩小" aria-label="缩小图谱" @click="zoomOut">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="M21 21l-4.3-4.3" />
              <path d="M8 11h6" />
            </svg>
          </button>
        </div>

        <div v-if="activeNav === 'graph'" class="graph-legend-area">
          <div class="floating-legend">
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
          <div class="graph-floating-stats" aria-label="图谱统计">
            <span>{{ nodes.length }} 点</span>
            <span>{{ links.length }} 边</span>
          </div>
        </div>

        <section v-if="activeNav !== 'graph'" class="workspace-page">
          <div class="workspace-page-head">
            <div>
              <span class="sidebar-eyebrow">当前功能</span>
              <h2>{{ currentNavLabel }}</h2>
              <p>{{ currentNavHint }}</p>
            </div>
            <button class="return-graph-button" @click="switchNav('graph')">返回图谱</button>
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
              @training-submitted="onTrainingSubmitted"
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
import { knowledgeApi, graphApi } from '../api/index.js'
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
import { useClassroomHeatmap } from '../composables/useClassroomHeatmap.js'
import { useCourses } from '../composables/useCourses.js'
import { useGraphState } from '../composables/useGraphState.js'
import { useMastery } from '../composables/useMastery.js'
import { useToast } from '../composables/useToast.js'

const props = defineProps({ user: { type: Object, default: null } })
defineEmits(['logout', 'profile-updated'])
const { showToast } = useToast()

const roleLabel = computed(() => ({ student: '学生', teacher: '教师', admin: '管理员' }[props.user?.role] || '学生'))
const canEditGraph = computed(() => props.user?.role === 'teacher' || props.user?.role === 'admin')
const displayName = computed(() => props.user?.nickname || props.user?.name || props.user?.email || '未命名用户')
const userInitials = computed(() => String(displayName.value || 'U').trim().slice(0, 2).toUpperCase())

function navIcon(content) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${content}</svg>`
}

const NAV_ICONS = {
  graph: navIcon('<circle cx="6" cy="7" r="2.2" /><circle cx="18" cy="6" r="2.2" /><circle cx="12" cy="18" r="2.2" /><path d="M8 8l8-1" /><path d="M7 9l4 7" /><path d="M17 8l-4 8" />'),
  browse: navIcon('<rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 9h18" /><path d="M7 7h.01" /><path d="M10 7h.01" />'),
  qa: navIcon('<path d="M4 5h16v10H8l-4 4z" /><path d="M8 9h8" /><path d="M8 12h5" />'),
  path: navIcon('<circle cx="5" cy="19" r="2" /><circle cx="19" cy="5" r="2" /><path d="M7 19h3a4 4 0 0 0 0-8h4a4 4 0 0 0 4-4" />'),
  errors: navIcon('<path d="M12 3l9 16H3z" /><path d="M12 9v4" /><path d="M12 17h.01" />'),
  paper: navIcon('<path d="M6 3h9l3 3v15H6z" /><path d="M14 3v4h4" /><path d="M9 12h6" /><path d="M9 16h4" />'),
  resources: navIcon('<path d="M4 6h6l2 2h8v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /><path d="M4 10h16" />'),
  teaching: navIcon('<path d="M4 5h16v11H4z" /><path d="M8 21l4-5 4 5" /><path d="M12 16v5" /><path d="M8 9h8" /><path d="M8 12h5" />'),
  classReport: navIcon('<path d="M4 20V4" /><path d="M4 20h16" /><path d="M8 16v-5" /><path d="M12 16V8" /><path d="M16 16v-8" />'),
  review: navIcon('<path d="M5 4h14v16H5z" /><path d="M8 9l2 2 5-5" /><path d="M8 15h8" />'),
  manage: navIcon('<path d="M4 6h10" /><path d="M18 6h2" /><circle cx="16" cy="6" r="2" /><path d="M4 12h2" /><path d="M10 12h10" /><circle cx="8" cy="12" r="2" /><path d="M4 18h12" /><path d="M20 18h0" /><circle cx="18" cy="18" r="2" />'),
  admin: navIcon('<rect x="3" y="4" width="18" height="16" rx="2" /><path d="M7 15l3-3 3 2 4-6" /><path d="M7 18h10" />'),
  profile: navIcon('<circle cx="12" cy="8" r="4" /><path d="M4 20a8 8 0 0 1 16 0" />'),
}

const NAV_DEFS = {
  graph: { key: 'graph', icon: NAV_ICONS.graph, label: '知识图谱', hint: '全局关系视图' },
  browse: { key: 'browse', icon: NAV_ICONS.browse, label: '知识浏览', hint: '搜索与筛选节点' },
  qa: { key: 'qa', icon: NAV_ICONS.qa, label: 'AI 问答', hint: '结合图谱上下文答疑' },
  path: { key: 'path', icon: NAV_ICONS.path, label: '学习路径', hint: '推荐补习路线' },
  errors: { key: 'errors', icon: NAV_ICONS.errors, label: '错题本', hint: '错题溯源分析' },
  paper: { key: 'paper', icon: NAV_ICONS.paper, label: '智能组卷', hint: '薄弱点专项训练' },
  resources: { key: 'resources', icon: NAV_ICONS.resources, label: '资源库', hint: '资源管理与批量挂载' },
  teaching: { key: 'teaching', icon: NAV_ICONS.teaching, label: '备课教研', hint: '课件上传、抽取建图与命题统计' },
  classReport: { key: 'classReport', icon: NAV_ICONS.classReport, label: '班级报告', hint: '错题统计与精准教学' },
  review: { key: 'review', icon: NAV_ICONS.review, label: '主观题批阅', hint: '批阅待处理主观题' },
  manage: { key: 'manage', icon: NAV_ICONS.manage, label: '知识管理', hint: '维护节点与关系' },
  admin: { key: 'admin', icon: NAV_ICONS.admin, label: '数据看板', hint: '平台与知识库运营' },
  profile: { key: 'profile', icon: NAV_ICONS.profile, label: '个人中心', hint: '资料编辑与学习概览' },
}

const ROLE_NAV_KEYS = {
  student: ['graph', 'browse', 'qa', 'path', 'errors', 'paper'],
  teacher: ['graph', 'browse', 'qa', 'teaching', 'classReport', 'review', 'resources', 'manage'],
  admin: ['graph', 'browse', 'resources', 'manage', 'admin'],
}

const ROLE_NAV_GROUPS = {
  student: [
    { title: '学习地图', keys: ['graph', 'browse', 'path'] },
    { title: '学习助手', keys: ['qa'] },
    { title: '训练反馈', keys: ['paper', 'errors'] },
  ],
  teacher: [
    { title: '课程建设', keys: ['graph', 'browse', 'manage', 'resources', 'teaching'] },
    { title: '教学诊断', keys: ['classReport'] },
    { title: '教学干预', keys: ['review', 'qa'] },
  ],
  admin: [
    { title: '用户治理', keys: ['admin'] },
    { title: '图谱治理', keys: ['graph', 'browse', 'manage', 'resources'] },
  ],
}

const ROLE_ACTIONS = {
  student: {
    title: '完成学习闭环',
    text: '先看图谱定位薄弱点，再生成专项训练，错题会回流到掌握度。',
    cta: '开始专项训练',
    nav: 'paper',
  },
  teacher: {
    title: '诊断班级薄弱点',
    text: '从班级报告查看共性问题，再补资源、调题目、批阅主观题。',
    cta: '查看班级报告',
    nav: 'classReport',
  },
  admin: {
    title: '治理图谱质量',
    text: '检查用户、资源和知识图谱状态，及时处理孤立节点与数据风险。',
    cta: '打开数据看板',
    nav: 'admin',
  },
}

const navItems = computed(() => {
  const role = props.user?.role || 'student'
  return (ROLE_NAV_KEYS[role] || ROLE_NAV_KEYS.student).map(key => NAV_DEFS[key]).filter(Boolean)
})

const navGroups = computed(() => {
  const role = props.user?.role || 'student'
  return (ROLE_NAV_GROUPS[role] || ROLE_NAV_GROUPS.student)
    .map(group => ({
      ...group,
      items: group.keys.map(key => NAV_DEFS[key]).filter(Boolean),
    }))
    .filter(group => group.items.length)
})

const primaryAction = computed(() => ROLE_ACTIONS[props.user?.role || 'student'] || ROLE_ACTIONS.student)

const currentNav = computed(() => NAV_DEFS[activeNav.value] || NAV_DEFS.graph)
const currentNavLabel = computed(() => currentNav.value.label)
const currentNavHint = computed(() => currentNav.value.hint)

const graphRef = ref(null)
const pathRecommendRef = ref(null)
const activeNav = ref('graph')
const selectedNode = ref(null)
const selectedLink = ref(null)
const showNextAction = ref(true)
const { courses, currentCourseId, loadCourses, selectCourse: setCourse } = useCourses()
const userId = computed(() => props.user?.id || '')
const {
  nodes,
  links,
  categories,
  selectedCategory,
  highlightedPath,
  highlightedPaths,
  searchNodeId,
  graphPositions,
  currentGraphViewport,
  currentGraphLayoutMode,
  loadGraphPositions,
  onGraphViewportChange,
  onGraphLayoutChange,
  onNodePositionChange,
  fetchGraph,
  fetchCategories,
  clearPath,
  setPath,
  removeNodePosition,
} = useGraphState(currentCourseId, userId)
const { masteryMap, masteredIds, fetchMastery, updateLocalMastery } = useMastery(userId, currentCourseId)
const userRef = computed(() => props.user || null)
const {
  classes,
  currentClassId,
  heatmapData,
  heatmapMode,
  fetchClasses,
  onClassChange,
  toggleHeatmap,
} = useClassroomHeatmap(userRef, currentCourseId, fetchGraph)
const focusedNode = ref(null)
const graphEditMode = ref(false)
const exportMenuOpen = ref(false)
const courseMenuOpen = ref(false)
const classMenuOpen = ref(false)
const relationSourceId = ref('')
const relationDraftType = ref('PREREQUISITE')
const relationDraftWeight = ref(1)
const batchMode = ref(false)
const batchSelectedIds = ref([])
const form = ref({ name: '', category: '', difficulty: 1, estimated_time: 0, description: '' })
const relSource = ref('')
const relTarget = ref('')
const relType = ref('PREREQUISITE')

const currentCourseName = computed(() => {
  const course = courses.value.find(item => item.id === currentCourseId.value)
  if (course) return course.name
  return courses.value.length ? '请选择课程' : '暂无课程'
})

const currentClassName = computed(() => {
  if (!currentClassId.value) return '全部班级'
  return classes.value.find(item => item.id === currentClassId.value)?.name || '全部班级'
})

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

function recordGraphViewport() {
  const viewport = graphRef.value?.getViewport?.()
  if (viewport) onGraphViewportChange(viewport)
}

function toggleGraphEdit(force) {
  if (!canEditGraph.value) return
  graphEditMode.value = typeof force === 'boolean' ? force : !graphEditMode.value
  activeNav.value = 'graph'
  exportMenuOpen.value = false
  if (!graphEditMode.value) {
    selectedLink.value = null
    relationSourceId.value = ''
    batchMode.value = false
    batchSelectedIds.value = []
  }
}

function isNavAllowed(key) {
  return key === 'profile' || navItems.value.some(item => item.key === key)
}

function switchNav(key) {
  const nextKey = isNavAllowed(key) ? key : 'graph'
  if (activeNav.value === 'graph' && nextKey !== 'graph') recordGraphViewport()
  activeNav.value = nextKey
  exportMenuOpen.value = false
  courseMenuOpen.value = false
  classMenuOpen.value = false
}

function onNavClick(key) {
  switchNav(activeNav.value === key && key !== 'graph' ? 'graph' : key)
}

async function selectCourse(courseId) {
  recordGraphViewport()
  await setCourse(courseId, onCourseChange)
}

async function chooseCourse(courseId) {
  courseMenuOpen.value = false
  classMenuOpen.value = false
  await selectCourse(courseId)
}

async function chooseClass(classId) {
  currentClassId.value = classId
  classMenuOpen.value = false
  courseMenuOpen.value = false
  await onClassChange()
}

async function onCourseChange() {
  selectedNode.value = null
  selectedLink.value = null
  relationSourceId.value = ''
  batchSelectedIds.value = []
  clearPath()
  selectedCategory.value = ''
  loadGraphPositions()
  await fetchGraph()
  await fetchCategories()
  await fetchMastery()
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
  setPath(pathNodes, pathGroups)
}

async function onShowRoadmap(targetId) {
  if (!isNavAllowed('path')) return
  switchNav('path')
  await nextTick()
  if (pathRecommendRef.value) pathRecommendRef.value.fetchPath(targetId)
}

function onClearPath() {
  clearPath()
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
    const level = updateLocalMastery(nodeId, score)
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

async function onTrainingSubmitted() {
  await fetchMastery()
  await fetchGraph()
  if (selectedNode.value && pathRecommendRef.value?.fetchPath) {
    await pathRecommendRef.value.fetchPath(selectedNode.value.id)
  }
}

function fitGraph() {
  if (graphRef.value?.fitToScreen) graphRef.value.fitToScreen()
}

function zoomIn() {
  if (graphRef.value?.zoomBy) graphRef.value.zoomBy(1.18)
}

function zoomOut() {
  if (graphRef.value?.zoomBy) graphRef.value.zoomBy(0.86)
}

function exportGraph(format) {
  exportMenuOpen.value = false
  if (format === 'svg') graphRef.value?.exportSVG?.()
  else if (format === 'json') graphRef.value?.exportJSON?.()
  else if (format === 'csv') graphRef.value?.exportCSV?.()
}

async function onSaveNode(node, payload) {
  if (!node?.id) return
  try {
    const updated = await knowledgeApi.update(node.id, payload)
    nodes.value = nodes.value.map(n => n.id === updated.id ? updated : n)
    selectedNode.value = updated
    await fetchCategories()
  } catch (err) {
    showToast(err.normalizedMessage || '保存知识点失败', 'error')
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
  } catch (err) {
    showToast(err.normalizedMessage || '建立关系失败', 'error')
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
  } catch (err) {
    showToast(err.normalizedMessage || '保存关系失败', 'error')
  }
}

async function onDeleteLink(link) {
  if (!link || !confirm('确认删除该关系？')) return
  try {
    await graphApi.deleteRelation(normalizeId(link.source), normalizeId(link.target), link.type)
    selectedLink.value = null
    await fetchGraph()
  } catch (err) {
    showToast(err.normalizedMessage || '删除关系失败', 'error')
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
  } catch (err) {
    showToast(err.normalizedMessage || '批量更新失败', 'error')
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
  } catch (err) {
    showToast(err.normalizedMessage || '批量删除失败', 'error')
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
  } catch (err) {
    showToast(err.normalizedMessage || '创建知识点失败', 'error')
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
  } catch (err) {
    showToast(err.normalizedMessage || '创建失败', 'error')
  }
}

async function onDeleteNode(node = selectedNode.value) {
  if (!node || !confirm('确认删除：' + node.name + '？')) return
  try {
    await knowledgeApi.delete(node.id)
    removeNodePosition(node.id)
    selectedNode.value = null
    selectedLink.value = null
    batchSelectedIds.value = batchSelectedIds.value.filter(id => id !== node.id)
    await fetchGraph()
    await fetchCategories()
  } catch (err) {
    showToast(err.normalizedMessage || '删除失败', 'error')
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
  } catch (err) {
    showToast(err.normalizedMessage || '建立关系失败', 'error')
  }
}

onMounted(async () => {
  await loadCourses(onCourseChange)
  await fetchClasses()
})
</script>
