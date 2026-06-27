<template>
  <div class="teaching-research">
    <div v-if="!courseId" class="empty-state">请先选择课程</div>

    <template v-else>
      <section class="prep-panel prep-hero">
        <div>
          <span class="panel-eyebrow">备课教研</span>
          <h3>课程知识体系构建与命题分析</h3>
          <p>围绕当前课程完成思维导图导出、题库覆盖统计、课件教辅上传和材料自动建图。</p>
        </div>
        <button @click="downloadMindmap" :disabled="busy">导出思维导图</button>
      </section>

      <section class="prep-grid">
        <article class="prep-panel prep-stats">
          <div class="section-head">
            <div>
              <h3>历年出题频次 / 分值占比</h3>
              <p>基于题库中 Question 与知识点的 TESTS 关系统计。</p>
            </div>
            <button class="secondary small" @click="fetchStats" :disabled="busy">刷新</button>
          </div>

          <div class="prep-stat-cards">
            <div class="stat-card">
              <div class="stat-num">{{ stats.summary?.covered_nodes || 0 }}</div>
              <div class="stat-label">覆盖知识点</div>
            </div>
            <div class="stat-card">
              <div class="stat-num">{{ stats.summary?.question_bindings || 0 }}</div>
              <div class="stat-label">出题频次</div>
            </div>
            <div class="stat-card">
              <div class="stat-num">{{ stats.summary?.total_score || 0 }}</div>
              <div class="stat-label">累计分值</div>
            </div>
          </div>

          <div v-if="!stats.nodes?.length" class="empty-state compact">暂无题库统计，请先录入题目并绑定知识点。</div>
          <div v-else class="stats-table">
            <div class="stats-row stats-head">
              <span>知识点</span><span>频次</span><span>频次占比</span><span>分值占比</span>
            </div>
            <div v-for="item in stats.nodes.slice(0, 12)" :key="item.id" class="stats-row">
              <span class="stat-node">{{ item.name }}</span>
              <span>{{ item.frequency }}</span>
              <span><b :style="{ width: item.frequency_ratio + '%' }"></b>{{ item.frequency_ratio }}%</span>
              <span><b :style="{ width: item.score_ratio + '%' }"></b>{{ item.score_ratio }}%</span>
            </div>
          </div>
        </article>

        <article class="prep-panel">
          <div class="section-head">
            <div>
              <h3>课件 / 教辅上传</h3>
              <p>上传后自动登记为课程文档资源，可直接挂载知识点。</p>
            </div>
          </div>

          <div class="form-row">
            <label>资源标题</label>
            <input v-model.trim="uploadForm.title" placeholder="例如：导数专题课件" />
          </div>
          <div class="form-row">
            <label>文件</label>
            <input type="file" accept=".pdf,.ppt,.pptx,.doc,.docx,.xls,.xlsx,.txt,.md" @change="onUploadFileChange" />
          </div>
          <div class="form-row">
            <label>挂载知识点</label>
            <select v-model="uploadForm.node_ids" multiple size="6">
              <option v-for="node in nodes" :key="node.id" :value="node.id">{{ node.name }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>说明</label>
            <textarea v-model.trim="uploadForm.description" rows="3" placeholder="用途、适用课时或教研备注"></textarea>
          </div>
          <button class="full-width" @click="uploadResource" :disabled="!uploadFile || busy">上传课件 / 教辅</button>
        </article>

        <article class="prep-panel">
          <div class="section-head">
            <div>
              <h3>LLM 自动抽取知识点</h3>
              <p>粘贴教案、讲义或教材片段，生成知识点和前置关系草案。</p>
            </div>
          </div>

          <div class="form-row">
            <label>抽取分类</label>
            <input v-model.trim="extractCategory" placeholder="例如：高等数学-导数" />
          </div>
          <div class="form-row">
            <label>教学文本</label>
            <textarea v-model.trim="extractText" rows="8" placeholder="粘贴课程目标、章节目录、教案正文或教学材料内容"></textarea>
          </div>
          <div class="form-actions">
            <button @click="extractKnowledge" :disabled="!extractText || busy">抽取草案</button>
            <button class="secondary" @click="commitExtractedText" :disabled="!extractText || busy">抽取并写入图谱</button>
          </div>
        </article>

        <article class="prep-panel">
          <div class="section-head">
            <div>
              <h3>课程大纲 PDF / PPT 自动建图</h3>
              <p>支持 PPTX、DOCX、TXT/MD；PDF 会尽力读取文本内容。</p>
            </div>
          </div>

          <div class="form-row">
            <label>大纲分类</label>
            <input v-model.trim="outlineCategory" placeholder="例如：课程大纲" />
          </div>
          <div class="form-row">
            <label>大纲文件</label>
            <input type="file" accept=".pdf,.ppt,.pptx,.doc,.docx,.txt,.md" @change="onOutlineFileChange" />
          </div>
          <div class="form-actions">
            <button class="secondary" @click="previewOutline" :disabled="!outlineFile || busy">预览草案</button>
            <button @click="importOutline" :disabled="!outlineFile || busy">自动建图</button>
          </div>
        </article>
      </section>

      <section v-if="draft.nodes?.length" class="prep-panel draft-panel">
        <div class="section-head">
          <div>
            <h3>抽取草案</h3>
            <p>{{ draft.source === 'llm' ? 'LLM 抽取结果' : '规则抽取结果' }} · {{ draft.nodes.length }} 个知识点 · {{ draft.relations?.length || 0 }} 条关系</p>
          </div>
          <button class="secondary small" @click="draft = { nodes: [], relations: [] }">清空</button>
        </div>

        <div class="draft-layout">
          <div>
            <h4>知识点</h4>
            <div class="draft-list">
              <div v-for="node in draft.nodes" :key="node.name" class="draft-item">
                <b>{{ node.name }}</b>
                <span>{{ node.category }} · 难度 {{ node.difficulty || 1 }}</span>
              </div>
            </div>
          </div>
          <div>
            <h4>关系</h4>
            <div class="draft-list">
              <div v-for="(rel, index) in draft.relations || []" :key="index" class="draft-item">
                <b>{{ rel.source }} → {{ rel.target }}</b>
                <span>{{ rel.type || 'PREREQUISITE' }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { teachingApi } from '../api/index.js'

const props = defineProps({
  courseId: { type: String, default: '' },
  nodes: { type: Array, default: () => [] },
})

const emit = defineEmits(['graph-updated'])

const busy = ref(false)
const stats = ref({ summary: {}, nodes: [], by_type: [] })
const uploadFile = ref(null)
const outlineFile = ref(null)
const extractText = ref('')
const extractCategory = ref('LLM 自动抽取')
const outlineCategory = ref('课程大纲')
const draft = ref({ nodes: [], relations: [] })

const uploadForm = reactive({
  title: '',
  description: '',
  node_ids: [],
})

watch(() => props.courseId, () => {
  draft.value = { nodes: [], relations: [] }
  fetchStats()
}, { immediate: true })

onMounted(fetchStats)

function onUploadFileChange(event) {
  uploadFile.value = event.target.files?.[0] || null
  if (uploadFile.value && !uploadForm.title) uploadForm.title = uploadFile.value.name.replace(/\.[^.]+$/, '')
}

function onOutlineFileChange(event) {
  outlineFile.value = event.target.files?.[0] || null
}

async function fetchStats() {
  if (!props.courseId) return
  try {
    stats.value = await teachingApi.questionStats(props.courseId)
  } catch {
    stats.value = { summary: {}, nodes: [], by_type: [] }
  }
}

async function downloadMindmap() {
  if (!props.courseId) return
  busy.value = true
  try {
    const blob = await teachingApi.exportMindmap(props.courseId)
    downloadBlob(blob, 'course-mindmap.mm')
  } catch (err) {
    alert(err.normalizedMessage || '导出思维导图失败')
  } finally {
    busy.value = false
  }
}

async function uploadResource() {
  if (!uploadFile.value || !props.courseId) return
  busy.value = true
  try {
    const formData = new FormData()
    formData.append('course_id', props.courseId)
    formData.append('file', uploadFile.value)
    formData.append('title', uploadForm.title || uploadFile.value.name)
    formData.append('description', uploadForm.description)
    uploadForm.node_ids.forEach(id => formData.append('node_ids', id))
    await teachingApi.uploadResource(formData)
    uploadFile.value = null
    uploadForm.title = ''
    uploadForm.description = ''
    uploadForm.node_ids = []
    alert('上传成功')
  } catch (err) {
    alert(err.normalizedMessage || '上传失败')
  } finally {
    busy.value = false
  }
}

async function extractKnowledge() {
  if (!extractText.value || !props.courseId) return
  busy.value = true
  try {
    draft.value = await teachingApi.extractKnowledge({
      course_id: props.courseId,
      text: extractText.value,
      category: extractCategory.value || 'LLM 自动抽取',
    })
  } catch (err) {
    alert(err.normalizedMessage || '抽取失败')
  } finally {
    busy.value = false
  }
}

async function commitExtractedText() {
  if (!extractText.value || !props.courseId) return
  busy.value = true
  try {
    const formData = new FormData()
    formData.append('course_id', props.courseId)
    formData.append('text', extractText.value)
    formData.append('category', extractCategory.value || 'LLM 自动抽取')
    const result = await teachingApi.importOutline(formData)
    draft.value = { nodes: result.nodes || [], relations: result.relations || [], source: result.source }
    emit('graph-updated')
    alert(`写入完成：${result.created_nodes || 0} 个知识点，${result.created_relations || 0} 条关系`)
  } catch (err) {
    alert(err.normalizedMessage || '写入图谱失败')
  } finally {
    busy.value = false
  }
}

async function previewOutline() {
  await submitOutline(false)
}

async function importOutline() {
  await submitOutline(true)
}

async function submitOutline(commit) {
  if (!outlineFile.value || !props.courseId) return
  busy.value = true
  try {
    const formData = new FormData()
    formData.append('course_id', props.courseId)
    formData.append('file', outlineFile.value)
    formData.append('category', outlineCategory.value || '课程大纲')
    formData.append('commit', commit ? 'true' : 'false')
    const result = await teachingApi.importOutline(formData)
    draft.value = { nodes: result.nodes || [], relations: result.relations || [], source: result.source }
    if (commit) {
      emit('graph-updated')
      alert(`建图完成：${result.created_nodes || 0} 个知识点，${result.created_relations || 0} 条关系`)
    }
  } catch (err) {
    alert(err.normalizedMessage || '课程大纲处理失败')
  } finally {
    busy.value = false
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
</script>
