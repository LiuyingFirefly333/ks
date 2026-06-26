<template>
  <div class="test-paper">
    <div class="test-paper-actions">
      <button @click="generate" :disabled="loading || !studentId">生成在线训练</button>
      <select v-model.number="questionCount" :disabled="loading">
        <option :value="5">5 题</option>
        <option :value="10">10 题</option>
        <option :value="15">15 题</option>
      </select>
      <span v-if="paperId" class="test-meta">
        {{ questions.length }} 题 · 覆盖 {{ weakNodes.length }} 个薄弱知识点
      </span>
    </div>

    <div v-if="loading" class="loading-spinner"></div>

    <div v-if="!loading && !paperId" class="empty-state">
      基于薄弱知识点、错题记录和题库，自动生成可在线作答的专项训练。
    </div>

    <div v-if="weakNodes.length" class="test-weak-nodes">
      <div class="section-title">薄弱知识点</div>
      <span
        v-for="n in weakNodes"
        :key="n.id"
        class="weak-node-tag"
        @click="$emit('locate-node', n.id)"
      >
        {{ n.name }}
      </span>
    </div>

    <div v-if="paperId && questions.length" class="test-exercises online-paper">
      <div class="section-title">
        在线训练题 <span>{{ questions.length }}</span>
      </div>

      <article v-for="(question, idx) in questions" :key="question.id" class="test-question-card">
        <div class="test-question-head">
          <div class="test-ex-num">{{ idx + 1 }}</div>
          <div class="test-question-title">
            <b>{{ typeLabel(question.type) }} · {{ question.score || 5 }} 分</b>
            <span @click="$emit('locate-node', question.node_id)">
              {{ question.node_name || firstNodeName(question) }}
            </span>
          </div>
          <span class="cat-tag">难度 {{ question.difficulty || 1 }}</span>
        </div>

        <div class="test-stem">{{ question.stem }}</div>

        <div v-if="question.type === 'single_choice' || question.type === 'true_false'" class="answer-options">
          <label v-for="option in normalizedOptions(question)" :key="question.id + option.key" class="answer-option">
            <input
              type="radio"
              :name="question.id"
              :value="option.key"
              v-model="answers[question.id]"
              :disabled="submitted"
            />
            <span>{{ option.key }}. {{ option.text }}</span>
          </label>
        </div>

        <div v-else-if="question.type === 'multiple_choice'" class="answer-options">
          <label v-for="option in normalizedOptions(question)" :key="question.id + option.key" class="answer-option">
            <input
              type="checkbox"
              :value="option.key"
              :checked="multiAnswer(question.id).includes(option.key)"
              :disabled="submitted"
              @change="toggleMulti(question.id, option.key)"
            />
            <span>{{ option.key }}. {{ option.text }}</span>
          </label>
        </div>

        <textarea
          v-else
          v-model.trim="answers[question.id]"
          :disabled="submitted"
          rows="3"
          placeholder="在这里输入答案"
        ></textarea>

        <div v-if="submitted" class="answer-result" :class="resultClass(question.id)">
          <b>{{ resultText(question.id) }}</b>
          <span v-if="attemptByQuestion(question.id)?.correct_answer">参考答案：{{ attemptByQuestion(question.id).correct_answer }}</span>
          <p v-if="attemptByQuestion(question.id)?.analysis">{{ attemptByQuestion(question.id).analysis }}</p>
        </div>
      </article>

      <div class="test-submit-bar">
        <button @click="submit" :disabled="submitted || loading || !questions.length">提交批改</button>
        <button class="secondary" @click="generate" :disabled="loading">重新生成</button>
        <span v-if="submitted" class="test-score">
          客观题 {{ result.objective_score }} / {{ result.total_score }} 分
          <b v-if="result.subjective_pending"> · {{ result.subjective_pending }} 题待教师批阅</b>
        </span>
      </div>
    </div>

    <div v-if="paperId && !questions.length && !loading" class="empty-state">
      当前薄弱知识点暂无可用题目，请先在题库中添加题目。
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { examApi } from '../api/index.js'

const props = defineProps({
  studentId: { type: String, default: '' },
  courseId: { type: String, default: '' },
})
defineEmits(['locate-node'])

const loading = ref(false)
const paperId = ref('')
const weakNodes = ref([])
const questions = ref([])
const submitted = ref(false)
const result = ref({})
const questionCount = ref(10)
const answers = reactive({})

async function generate() {
  if (!props.studentId) return
  loading.value = true
  submitted.value = false
  result.value = {}
  clearAnswers()
  try {
    const data = await examApi.generateTest(props.studentId, props.courseId, questionCount.value)
    paperId.value = data.id || ''
    weakNodes.value = data.weak_nodes || []
    questions.value = data.questions || []
  } catch {
    paperId.value = ''
    weakNodes.value = []
    questions.value = []
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!paperId.value) return
  loading.value = true
  try {
    const payload = questions.value.map(question => ({
      question_id: question.id,
      answer: question.type === 'multiple_choice'
        ? multiAnswer(question.id)
        : answers[question.id] || '',
    }))
    result.value = await examApi.submitTest(paperId.value, payload)
    submitted.value = true
  } catch (err) {
    alert(err.normalizedMessage || '提交失败')
  } finally {
    loading.value = false
  }
}

function clearAnswers() {
  for (const key of Object.keys(answers)) delete answers[key]
}

function normalizedOptions(question) {
  if (question.type === 'true_false' && (!question.options || !question.options.length)) {
    return [
      { key: 'T', text: '正确' },
      { key: 'F', text: '错误' },
    ]
  }
  return (question.options || []).map((item, index) => {
    if (typeof item === 'object') return { key: item.key || String.fromCharCode(65 + index), text: item.text || item.label || '' }
    return { key: String.fromCharCode(65 + index), text: String(item) }
  })
}

function multiAnswer(id) {
  if (!Array.isArray(answers[id])) answers[id] = []
  return answers[id]
}

function toggleMulti(id, key) {
  const current = new Set(multiAnswer(id))
  if (current.has(key)) current.delete(key)
  else current.add(key)
  answers[id] = [...current].sort()
}

function attemptByQuestion(questionId) {
  return (result.value.attempts || []).find(item => item.question_id === questionId)
}

function resultClass(questionId) {
  const attempt = attemptByQuestion(questionId)
  if (!attempt) return ''
  if (attempt.status === 'pending_review') return 'pending'
  return attempt.is_correct ? 'correct' : 'wrong'
}

function resultText(questionId) {
  const attempt = attemptByQuestion(questionId)
  if (!attempt) return ''
  if (attempt.status === 'pending_review') return '待教师批阅'
  return attempt.is_correct ? `正确，得 ${attempt.score} 分` : '错误，已加入错题本'
}

function firstNodeName(question) {
  return question.knowledge_nodes?.[0]?.name || '综合题'
}

function typeLabel(type) {
  return {
    single_choice: '单选题',
    multiple_choice: '多选题',
    true_false: '判断题',
    blank: '填空题',
    subjective: '主观题',
  }[type] || '题目'
}
</script>
