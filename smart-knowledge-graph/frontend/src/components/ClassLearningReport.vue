<template>
  <div class="class-report">
    <div class="report-toolbar">
      <div class="form-row">
        <label>班级</label>
        <select v-model="selectedClassId" @change="loadReport">
          <option value="">请选择班级</option>
          <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
      </div>
      <button @click="loadReport" :disabled="loading || !selectedClassId">刷新报告</button>
      <button class="secondary" @click="downloadExcel" :disabled="loading || !selectedClassId">导出 Excel</button>
    </div>

    <div v-if="loading" class="loading-spinner"></div>
    <div v-else-if="!selectedClassId" class="empty-state">选择班级后生成学情统计与教学建议。</div>
    <div v-else-if="!report" class="empty-state">暂无报告数据。</div>

    <template v-else>
      <section class="report-summary-grid">
        <div v-for="item in summaryItems" :key="item.label" class="report-stat">
          <strong>{{ item.value }}</strong>
          <span>{{ item.label }}</span>
        </div>
      </section>

      <section class="report-panel">
        <div class="section-head">
          <h3>高频易错知识点</h3>
          <span>{{ topNodes.length }} 项</span>
        </div>
        <div v-if="!topNodes.length" class="empty-state compact">暂无错题沉淀。</div>
        <div v-else class="report-table">
          <div class="report-table-head">
            <span>知识点</span><span>错题</span><span>学生</span><span>掌握度</span><span>操作</span>
          </div>
          <div v-for="node in topNodes" :key="node.node_id" class="report-table-row">
            <span>
              <b>{{ node.name }}</b>
              <small>{{ node.category || '未分类' }}</small>
            </span>
            <span>{{ node.error_count }}</span>
            <span>{{ node.student_count }}</span>
            <span>{{ node.avg_score || 0 }} 分</span>
            <button class="secondary small" @click="$emit('locate-node', node.node_id)">定位</button>
          </div>
        </div>
      </section>

      <section class="report-panel">
        <div class="section-head">
          <h3>专题教学建议</h3>
          <span>{{ suggestions.length }} 条</span>
        </div>
        <div v-if="!suggestions.length" class="empty-state compact">暂无明显专题建议。</div>
        <article v-for="item in suggestions" :key="item.node_id || item.title" class="suggestion-card">
          <div>
            <b>{{ item.title }}</b>
            <small>{{ item.reason }}</small>
          </div>
          <p>{{ item.strategy }}</p>
          <div class="suggestion-actions">
            <span v-for="action in item.actions" :key="action" class="path-res-tag">{{ action }}</span>
            <span class="path-res-tag time">{{ item.suggested_minutes }} 分钟</span>
          </div>
        </article>
      </section>

      <section class="report-panel">
        <div class="section-head">
          <h3>学生错题统计</h3>
          <span>{{ studentStats.length }} 人</span>
        </div>
        <div class="student-error-list">
          <div v-for="student in studentStats" :key="student.id" class="student-error-item">
            <b>{{ student.name }}</b>
            <span>{{ student.error_count }} 条错题</span>
            <small>{{ student.weak_node_count }} 个相关知识点</small>
          </div>
        </div>
      </section>

      <section class="report-panel">
        <div class="section-head">
          <h3>教学建议文档</h3>
          <span>可复制到教案</span>
        </div>
        <pre class="teaching-doc">{{ report.teaching_document }}</pre>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { analyticsApi } from '../api/index.js'

const props = defineProps({
  classes: { type: Array, default: () => [] },
  classId: { type: String, default: '' },
  courseId: { type: String, default: '' },
})

defineEmits(['locate-node'])

const selectedClassId = ref(props.classId || '')
const loading = ref(false)
const report = ref(null)

const topNodes = computed(() => report.value?.top_error_nodes || [])
const suggestions = computed(() => report.value?.teaching_suggestions || [])
const studentStats = computed(() => report.value?.student_error_stats || [])
const summaryItems = computed(() => {
  const summary = report.value?.summary || {}
  return [
    { label: '学生数', value: summary.student_count || 0 },
    { label: '错题总数', value: summary.total_errors || 0 },
    { label: '涉及学生', value: summary.affected_students || 0 },
    { label: '高频易错点', value: summary.high_frequency_nodes || 0 },
    { label: '平均掌握度', value: `${summary.avg_class_score || 0} 分` },
  ]
})

watch(() => props.classId, value => {
  selectedClassId.value = value || ''
  if (selectedClassId.value) loadReport()
})

watch(() => props.courseId, () => {
  if (selectedClassId.value) loadReport()
})

async function loadReport() {
  if (!selectedClassId.value) {
    report.value = null
    return
  }
  loading.value = true
  try {
    report.value = await analyticsApi.classReport(selectedClassId.value, props.courseId)
  } catch {
    report.value = null
  } finally {
    loading.value = false
  }
}

async function downloadExcel() {
  if (!selectedClassId.value) return
  const blob = await analyticsApi.exportClassReport(selectedClassId.value, props.courseId)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${report.value?.class?.name || '班级'}-学情报告.xls`
  link.click()
  URL.revokeObjectURL(url)
}

if (selectedClassId.value) loadReport()
</script>
