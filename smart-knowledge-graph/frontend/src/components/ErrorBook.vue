<template>
  <div class="error-book">
    <div class="panel-actions">
      <button class="secondary" @click="fetchErrors" :disabled="loading">刷新错题</button>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-if="!loading && errors.length === 0" class="empty-state">
      暂无错题记录。完成练习后，错题会在这里自动沉淀。
    </div>

    <div v-for="err in errors" :key="err.id" class="error-card">
      <div class="error-card-header">
        <span class="error-node-badge" @click="$emit('locate-node', err.node_id)">
          {{ err.node_name }}
        </span>
        <span class="error-date">{{ fmtDate(err.created_at) }}</span>
        <button class="icon-button subtle" @click="onDelete(err.id)" title="删除">×</button>
      </div>
      <div class="error-question">{{ err.question }}</div>
      <div class="error-answers">
        <div class="error-ans wrong">你的答案：{{ err.student_answer || '未作答' }}</div>
        <div class="error-ans correct">正确答案：{{ err.correct_answer || '暂无' }}</div>
      </div>
      <div v-if="err.error_reason" class="error-reason">{{ err.error_reason }}</div>
      <button class="error-trace-btn" @click="onTrace(err)">
        {{ traceErrorId === err.id ? '收起溯源' : '知识点溯源' }}
      </button>

      <div v-if="traceErrorId === err.id" class="error-trace">
        <div v-if="traceLoading" class="loading-spinner"></div>
        <div v-else-if="traceData" class="trace-report">
          <section class="trace-node">
            <div>
              <span class="trace-label muted">错题考点</span>
              <h3>{{ traceData.node?.name || err.node_name }}</h3>
              <p>{{ traceData.node?.description || '暂无考点说明' }}</p>
            </div>
            <button class="secondary small" @click="$emit('locate-node', traceData.node?.id || err.node_id)">
              定位图谱
            </button>
          </section>

          <section class="trace-stats-grid">
            <div class="trace-stat">
              <strong>{{ traceStats.question_count || 0 }}</strong>
              <span>题库考查</span>
            </div>
            <div class="trace-stat">
              <strong>{{ traceStats.error_count || 0 }}</strong>
              <span>历史错题</span>
            </div>
            <div class="trace-stat">
              <strong>{{ traceStats.avg_difficulty || 0 }}</strong>
              <span>平均难度</span>
            </div>
            <div class="trace-stat">
              <strong>{{ traceStats.total_score || 0 }}</strong>
              <span>覆盖分值</span>
            </div>
          </section>

          <section class="trace-section">
            <div class="trace-section-head">
              <h4>完整关联知识网络</h4>
              <span>{{ traceGraph.nodes.length }} 个节点 / {{ traceGraph.links.length }} 条关系</span>
            </div>
            <div class="trace-network-grid">
              <TraceNodeList
                title="前置知识"
                :nodes="tracePrerequisites"
                empty-text="暂无前置知识"
                @locate="id => $emit('locate-node', id)"
              />
              <TraceNodeList
                title="后续依赖"
                :nodes="traceDependents"
                empty-text="暂无后续依赖"
                @locate="id => $emit('locate-node', id)"
              />
              <TraceNodeList
                title="相关知识"
                :nodes="traceRelated"
                empty-text="暂无相关知识"
                @locate="id => $emit('locate-node', id)"
              />
            </div>
            <div v-if="traceGraph.links.length" class="trace-link-list">
              <div v-for="link in traceGraph.links" :key="`${link.source}-${link.type}-${link.target}`" class="trace-link">
                <span>{{ link.source_name || link.source }}</span>
                <b>{{ relationLabel(link.type) }}</b>
                <span>{{ link.target_name || link.target }}</span>
              </div>
            </div>
          </section>

          <section class="trace-section trace-meta-grid">
            <div>
              <h4>历年考查频次</h4>
              <div v-if="traceYearFrequency.length || traceSourceFrequency.length" class="trace-frequency-list">
                <div v-for="item in traceYearFrequency" :key="item.year" class="trace-frequency-item">
                  <span>{{ item.year }} 年</span>
                  <b>{{ item.count }} 题</b>
                </div>
                <div v-for="item in traceSourceFrequency" :key="item.source" class="trace-frequency-item">
                  <span>{{ item.source }}</span>
                  <b>{{ item.count }} 题</b>
                </div>
              </div>
              <span v-else class="trace-muted">暂无来源数据</span>
            </div>
            <div>
              <h4>衍生题型</h4>
              <div class="trace-chip-row">
                <span v-for="type in traceStats.question_types" :key="type" class="trace-chip">
                  {{ questionTypeLabel(type) }}
                </span>
                <span v-if="!traceStats.question_types?.length" class="trace-muted">暂无题型数据</span>
              </div>
            </div>
          </section>

          <section class="trace-section">
            <div class="trace-section-head">
              <h4>高频错误原因</h4>
              <span>{{ traceReasons.length }} 类</span>
            </div>
            <div class="trace-reason-list">
              <div v-for="reason in traceReasons" :key="reason.reason" class="trace-reason-item">
                <span>{{ reason.reason }}</span>
                <b>{{ reason.count }} 次</b>
              </div>
            </div>
          </section>

          <section class="trace-section">
            <div class="trace-section-head">
              <h4>同类变式题自动推荐</h4>
              <span>{{ traceRecommended.length + traceExtensions.length }} 题</span>
            </div>
            <QuestionList
              :questions="traceRecommended"
              empty-text="当前考点暂无已入库同类题"
            />
            <div v-if="traceExtensions.length" class="trace-subtitle">关联知识拓展题</div>
            <QuestionList
              v-if="traceExtensions.length"
              :questions="traceExtensions"
              empty-text=""
            />
          </section>

          <section class="trace-section">
            <div class="trace-section-head">
              <h4>自动生成变式题</h4>
              <span>{{ traceGenerated.length }} 题</span>
            </div>
            <QuestionList
              :questions="traceGenerated"
              empty-text="暂无可生成变式题"
              generated
            />
          </section>
        </div>
        <div v-else class="empty-state compact">溯源数据加载失败，请稍后重试。</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, ref, onMounted } from 'vue'
import { examApi } from '../api/index.js'

const props = defineProps({
  studentId: { type: String, default: '' },
})
defineEmits(['locate-node'])

const errors = ref([])
const loading = ref(false)
const traceErrorId = ref(null)
const traceData = ref(null)
const traceLoading = ref(false)

const traceStats = computed(() => traceData.value?.exam_frequency || {})
const traceGraph = computed(() => traceData.value?.graph || { nodes: [], links: [] })
const tracePrerequisites = computed(() => traceData.value?.prerequisites || [])
const traceDependents = computed(() => traceData.value?.dependents || [])
const traceRelated = computed(() => traceData.value?.related_nodes || [])
const traceReasons = computed(() => traceData.value?.common_error_reasons || [])
const traceRecommended = computed(() => traceData.value?.recommended_questions || [])
const traceExtensions = computed(() => traceData.value?.extension_questions || [])
const traceGenerated = computed(() => traceData.value?.generated_variants || [])
const traceYearFrequency = computed(() => traceStats.value?.year_frequency || [])
const traceSourceFrequency = computed(() => traceStats.value?.source_frequency || [])

const TraceNodeList = defineComponent({
  props: {
    title: { type: String, required: true },
    nodes: { type: Array, default: () => [] },
    emptyText: { type: String, default: '暂无数据' },
  },
  emits: ['locate'],
  setup(componentProps, { emit }) {
    return () => h('div', { class: 'trace-node-list' }, [
      h('div', { class: 'trace-list-title' }, `${componentProps.title} ${componentProps.nodes.length}`),
      componentProps.nodes.length
        ? h('div', { class: 'trace-pill-row' }, componentProps.nodes.map(node =>
          h('button', {
            key: node.id,
            class: 'trace-item',
            onClick: () => emit('locate', node.id),
            title: node.description || node.name,
          }, node.name || node.id),
        ))
        : h('span', { class: 'trace-muted' }, componentProps.emptyText),
    ])
  },
})

const QuestionList = defineComponent({
  props: {
    questions: { type: Array, default: () => [] },
    emptyText: { type: String, default: '暂无题目' },
    generated: { type: Boolean, default: false },
  },
  setup(componentProps) {
    return () => componentProps.questions.length
      ? h('div', { class: 'trace-question-list' }, componentProps.questions.map(question =>
        h('article', { key: question.id || question.stem, class: ['trace-question-card', componentProps.generated ? 'generated' : ''] }, [
          h('div', { class: 'trace-question-meta' }, [
            h('span', questionTypeLabel(question.type)),
            h('span', `难度 ${question.difficulty || 1}`),
            h('span', `${question.score || 0} 分`),
            question.node?.name ? h('span', question.node.name) : null,
            question.source ? h('span', question.source) : null,
            question.exam_year ? h('span', `${question.exam_year} 年`) : null,
          ].filter(Boolean)),
          h('p', { class: 'trace-question-stem' }, question.stem || question.question || '暂无题干'),
          question.answer ? h('div', { class: 'trace-answer' }, `参考答案：${question.answer}`) : null,
          question.analysis ? h('div', { class: 'trace-analysis' }, question.analysis) : null,
        ]),
      ))
      : h('div', { class: 'empty-state compact' }, componentProps.emptyText)
  },
})

async function fetchErrors() {
  if (!props.studentId) return
  loading.value = true
  try {
    errors.value = await examApi.listErrors(props.studentId)
  } catch {
    errors.value = []
  }
  loading.value = false
}

async function onDelete(id) {
  try {
    await examApi.deleteError(id)
    errors.value = errors.value.filter(e => e.id !== id)
    if (traceErrorId.value === id) traceErrorId.value = null
  } catch {}
}

async function onTrace(err) {
  if (traceErrorId.value === err.id) {
    traceErrorId.value = null
    traceData.value = null
    return
  }
  traceErrorId.value = err.id
  traceLoading.value = true
  try {
    traceData.value = await examApi.errorTrace(err.id)
  } catch {
    traceData.value = null
  }
  traceLoading.value = false
}

function fmtDate(d) {
  if (!d) return ''
  try { return new Date(d).toLocaleDateString('zh-CN') } catch { return d }
}

function questionTypeLabel(type) {
  const labels = {
    choice: '选择题',
    single_choice: '单选题',
    multiple_choice: '多选题',
    blank: '填空题',
    judge: '判断题',
    subjective: '主观题',
    unknown: '未知题型',
  }
  return labels[type] || type || '未知题型'
}

function relationLabel(type) {
  const labels = {
    PREREQUISITE: '前置',
    RELATED_TO: '相关',
  }
  return labels[type] || type || '关系'
}

onMounted(() => fetchErrors())
</script>
