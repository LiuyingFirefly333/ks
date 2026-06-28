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

    <div v-if="paperId" class="learning-explain-card test-explain-card">
      <div>
        <span class="explain-label">出题依据</span>
        <p>{{ paperReason }}</p>
      </div>
      <div>
        <span class="explain-label">下一步动作</span>
        <button class="inline-action" @click="handleNextAction">
          {{ testNextAction }}
        </button>
      </div>
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

      <div v-if="submitted" class="learning-explain-card result-explain-card">
        <div>
          <span class="explain-label">结果解释</span>
          <p>{{ resultReason }}</p>
        </div>
        <div>
          <span class="explain-label">下一步动作</span>
          <button class="inline-action" @click="handleNextAction">
            {{ testNextAction }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="paperId && !questions.length && !loading" class="empty-state">
      当前薄弱知识点暂无可用题目，请先在题库中添加题目。
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { examApi } from '../api/index.js'
import { useToast } from '../composables/useToast.js'

const props = defineProps({
  studentId: { type: String, default: '' },
  courseId: { type: String, default: '' },
})
const emit = defineEmits(['locate-node', 'training-submitted'])
const { showToast } = useToast()

const loading = ref(false)
const paperId = ref('')
const weakNodes = ref([])
const questions = ref([])
const submitted = ref(false)
const result = ref({})
const paperReason = ref('')
const generatedNextAction = ref(null)
const questionCount = ref(10)
const answers = reactive({})

const wrongAttempts = computed(() => (result.value.attempts || []).filter(item => item.status !== 'pending_review' && !item.is_correct))
const resultReason = computed(() => {
  if (!submitted.value) return ''
  const totalObjective = (result.value.attempts || []).filter(item => item.status !== 'pending_review').length
  if (result.value.subjective_pending) {
    return `本次有 ${result.value.subjective_pending} 道主观题等待教师批阅，客观题已即时反馈。`
  }
  if (wrongAttempts.value.length) {
    const nodes = uniqueWrongNodeNames().slice(0, 3).join('、')
    return `本次错题集中在 ${nodes || '相关知识点'}，这些题已进入错题反馈链路。`
  }
  return totalObjective ? '本次客观题全部通过，说明当前训练覆盖的知识点掌握较稳定。' : '训练已提交，等待进一步反馈。'
})
const testNextAction = computed(() => {
  if (submitted.value && result.value.next_action?.label) return result.value.next_action.label
  return generatedNextAction.value?.label || '提交训练后查看复盘建议'
})

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
    paperReason.value = data.reason || buildPaperReason()
    generatedNextAction.value = data.next_action || null
  } catch {
    paperId.value = ''
    weakNodes.value = []
    questions.value = []
    paperReason.value = ''
    generatedNextAction.value = null
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
    emit('training-submitted', result.value)
  } catch (err) {
    showToast(err.normalizedMessage || '提交失败', 'error')
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

function buildPaperReason() {
  if (weakNodes.value.length) return `根据 ${weakNodes.value.length} 个薄弱/错题关联知识点生成专项训练。`
  return '当前薄弱点缺少可用题目，已从课程题库中选择综合训练题。'
}

function uniqueWrongNodeNames() {
  const names = []
  for (const attempt of wrongAttempts.value) {
    for (const node of attempt.knowledge_nodes || []) {
      if (node?.name && !names.includes(node.name)) names.push(node.name)
    }
  }
  return names
}

function handleNextAction() {
  if (submitted.value && wrongAttempts.value.length) {
    const node = wrongAttempts.value[0].knowledge_nodes?.[0]
    if (node?.id) {
      emit('locate-node', node.id)
      return
    }
  }
  const node = weakNodes.value[0]
  if (node?.id) emit('locate-node', node.id)
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
