<template>
  <div class="subjective-review">
    <div class="review-toolbar">
      <div class="form-row">
        <label>班级</label>
        <select v-model="filters.class_id" @change="loadReviews">
          <option value="">全部班级</option>
          <option v-for="cls in classes" :key="cls.id" :value="cls.id">{{ cls.name }}</option>
        </select>
      </div>
      <div class="form-row">
        <label>状态</label>
        <select v-model="filters.status" @change="loadReviews">
          <option value="pending_review">待批阅</option>
          <option value="graded">已批阅</option>
          <option value="all">全部</option>
        </select>
      </div>
      <button @click="loadReviews" :disabled="loading">刷新</button>
    </div>

    <div class="review-summary-grid">
      <div class="report-stat">
        <strong>{{ pendingCount }}</strong>
        <span>待批阅</span>
      </div>
      <div class="report-stat">
        <strong>{{ gradedCount }}</strong>
        <span>已批阅</span>
      </div>
      <div class="report-stat">
        <strong>{{ reviews.length }}</strong>
        <span>当前列表</span>
      </div>
    </div>

    <div v-if="loading" class="loading-spinner"></div>
    <div v-else-if="!reviews.length" class="empty-state">暂无需要处理的主观题作答。</div>

    <article v-for="item in reviews" :key="item.attempt.id" class="review-card">
      <div class="review-card-head">
        <div>
          <strong>{{ item.student.name || '未命名学生' }}</strong>
          <small>{{ item.class?.name || '未分班' }} · {{ item.paper?.title || '在线训练' }}</small>
        </div>
        <span class="review-status" :class="{ done: item.attempt.status === 'graded' }">
          {{ item.attempt.status === 'graded' ? '已批阅' : '待批阅' }}
        </span>
      </div>

      <div class="review-question">
        <b>题目</b>
        <p>{{ item.question.stem }}</p>
      </div>

      <div class="review-answer-grid">
        <section>
          <b>学生答案</b>
          <pre>{{ item.attempt.answer || '未作答' }}</pre>
        </section>
        <section>
          <b>参考答案 / 解析</b>
          <pre>{{ item.attempt.correct_answer || item.question.analysis || '暂无参考内容' }}</pre>
        </section>
      </div>

      <div v-if="item.knowledge_nodes?.length" class="review-node-row">
        <button
          v-for="node in item.knowledge_nodes"
          :key="node.id"
          class="path-res-tag button-tag"
          @click="$emit('locate-node', node.id)"
        >
          {{ node.name }}
        </button>
      </div>

      <div class="review-grade-box">
        <div class="form-row score-row">
          <label>得分 / {{ maxScore(item) }}</label>
          <input
            v-model.number="gradeForms[item.attempt.id].score"
            type="number"
            min="0"
            :max="maxScore(item)"
            :disabled="savingId === item.attempt.id"
          />
        </div>
        <div class="form-row feedback-row">
          <label>批阅反馈</label>
          <textarea
            v-model.trim="gradeForms[item.attempt.id].feedback"
            rows="2"
            placeholder="指出得分点、扣分点或后续复习建议"
            :disabled="savingId === item.attempt.id"
          ></textarea>
        </div>
        <button
          @click="submitGrade(item)"
          :disabled="savingId === item.attempt.id || !canSubmit(item)"
        >
          {{ savingId === item.attempt.id ? '提交中...' : '提交批阅' }}
        </button>
      </div>

      <div v-if="item.attempt.review_feedback" class="review-feedback">
        <b>已保存反馈：</b>{{ item.attempt.review_feedback }}
      </div>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { examApi } from '../api/index.js'

const props = defineProps({
  classes: { type: Array, default: () => [] },
  classId: { type: String, default: '' },
  courseId: { type: String, default: '' },
})

defineEmits(['locate-node'])

const loading = ref(false)
const savingId = ref('')
const reviews = ref([])
const filters = reactive({
  class_id: props.classId || '',
  status: 'pending_review',
})
const gradeForms = reactive({})

const pendingCount = computed(() => reviews.value.filter(item => item.attempt?.status !== 'graded').length)
const gradedCount = computed(() => reviews.value.filter(item => item.attempt?.status === 'graded').length)

watch(() => props.classId, value => {
  filters.class_id = value || ''
  loadReviews()
})

watch(() => props.courseId, () => loadReviews())

function maxScore(item) {
  return Number(item.max_score || item.attempt?.max_score || item.question?.score || 0)
}

function ensureForm(item) {
  const id = item.attempt.id
  if (!gradeForms[id]) {
    gradeForms[id] = {
      score: Number(item.attempt.score || 0),
      feedback: item.attempt.review_feedback || '',
    }
  }
}

function normalizeForms() {
  reviews.value.forEach(ensureForm)
}

async function loadReviews() {
  loading.value = true
  try {
    reviews.value = await examApi.listSubjectiveReviews({
      course_id: props.courseId || undefined,
      class_id: filters.class_id || undefined,
      status: filters.status,
    })
    normalizeForms()
  } catch {
    reviews.value = []
  } finally {
    loading.value = false
  }
}

function canSubmit(item) {
  const form = gradeForms[item.attempt.id]
  if (!form) return false
  const score = Number(form.score)
  return Number.isFinite(score) && score >= 0 && score <= maxScore(item)
}

async function submitGrade(item) {
  if (!canSubmit(item)) return
  const id = item.attempt.id
  const form = gradeForms[id]
  savingId.value = id
  try {
    const updated = await examApi.gradeSubjective(id, Number(form.score), form.feedback || '')
    reviews.value = reviews.value.map(row => row.attempt.id === id
      ? { ...row, ...updated, max_score: maxScore({ ...row, ...updated }) }
      : row)
    ensureForm(reviews.value.find(row => row.attempt.id === id))
  } catch (err) {
    alert(err.normalizedMessage || '批阅提交失败')
  } finally {
    savingId.value = ''
  }
}

onMounted(loadReviews)
</script>
