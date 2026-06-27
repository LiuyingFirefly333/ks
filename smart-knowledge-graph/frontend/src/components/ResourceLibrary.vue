<template>
  <div class="resource-library">
    <section class="resource-panel resource-form-panel">
      <div class="section-head">
        <div>
          <h3>新增资源</h3>
          <p>创建后可挂载到一个或多个知识点。</p>
        </div>
        <button class="secondary small" @click="migrateLegacy" :disabled="!courseId || loading">迁移旧资源</button>
      </div>

      <div class="form-row">
        <label>标题</label>
        <input v-model.trim="form.title" placeholder="例如：导数定义微课" />
      </div>
      <div class="form-row two-cols">
        <div>
          <label>类型</label>
          <select v-model="form.type">
            <option v-for="type in resourceTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
          </select>
        </div>
        <div>
          <label>状态</label>
          <select v-model="form.status">
            <option v-for="status in statuses" :key="status.value" :value="status.value">{{ status.label }}</option>
          </select>
        </div>
      </div>
      <div class="form-row">
        <label>链接</label>
        <input v-model.trim="form.url" placeholder="https://..." />
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
        <label>标签</label>
        <input v-model.trim="tagText" placeholder="基础, 例题, 高频" />
      </div>
      <div class="form-row">
        <label>描述</label>
        <textarea v-model.trim="form.description" rows="3" placeholder="资源适用场景、内容摘要或使用建议"></textarea>
      </div>
      <div class="form-row">
        <label>挂载知识点</label>
        <select v-model="form.node_ids" multiple size="6">
          <option v-for="node in nodes" :key="node.id" :value="node.id">{{ node.name }}</option>
        </select>
      </div>
      <button class="full-width" @click="createResource" :disabled="!form.title || loading">创建资源</button>
    </section>

    <section class="resource-panel resource-list-panel">
      <div class="resource-toolbar">
        <input v-model.trim="filters.q" placeholder="搜索标题、描述、链接或标签" @keyup.enter="fetchResources" />
        <select v-model="filters.type" @change="fetchResources">
          <option value="">全部类型</option>
          <option v-for="type in resourceTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
        </select>
        <select v-model="filters.status" @change="fetchResources">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status.value" :value="status.value">{{ status.label }}</option>
        </select>
        <button class="secondary" @click="fetchResources">刷新</button>
      </div>

      <div class="resource-batch-bar">
        <span>{{ selectedResourceIds.length }} 个资源 · {{ selectedNodeIds.length }} 个知识点</span>
        <select v-model="selectedNodeIds" multiple size="3">
          <option v-for="node in nodes" :key="node.id" :value="node.id">{{ node.name }}</option>
        </select>
        <button @click="batchAttach" :disabled="!selectedResourceIds.length || !selectedNodeIds.length">批量挂载</button>
        <button class="secondary" @click="batchPublish" :disabled="!selectedResourceIds.length">批量上线</button>
        <button class="secondary" @click="clearSelection" :disabled="!selectedResourceIds.length && !selectedNodeIds.length">清空</button>
      </div>

      <div v-if="loading" class="empty-state">资源加载中...</div>
      <div v-else-if="!resources.length" class="empty-state">暂无资源</div>
      <div v-else class="resource-list">
        <article v-for="resource in resources" :key="resource.id" class="resource-card">
          <label class="resource-select">
            <input type="checkbox" :checked="selectedResourceIds.includes(resource.id)" @change="toggleResource(resource.id)" />
            <span>{{ typeLabel(resource.type) }}</span>
          </label>
          <div class="resource-card-main">
            <div class="resource-card-head">
              <h4>{{ resource.title }}</h4>
              <span class="resource-status" :class="'status-' + (resource.status || 'draft')">{{ statusLabel(resource.status) }}</span>
            </div>
            <p v-if="resource.description">{{ resource.description }}</p>
            <a v-if="resource.url" :href="resource.url" target="_blank" class="resource-url">{{ resource.url }}</a>
            <div class="resource-meta">
              <span v-if="resource.estimated_time">{{ resource.estimated_time }} 分钟</span>
              <span>难度 {{ resource.difficulty || 1 }}</span>
              <span v-for="tag in resource.tags || []" :key="resource.id + tag">{{ tag }}</span>
            </div>
            <div class="resource-bound">
              <span>已挂载：</span>
              <b>{{ boundNodeNames(resource) }}</b>
            </div>
          </div>
          <div class="resource-actions">
            <select :value="resource.status || 'draft'" @change="updateStatus(resource, $event.target.value)">
              <option v-for="status in statuses" :key="status.value" :value="status.value">{{ status.label }}</option>
            </select>
            <button class="danger small" @click="deleteResource(resource)">删除</button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { resourceApi } from '../api/index.js'
import { useToast } from '../composables/useToast.js'

const props = defineProps({
  courseId: { type: String, default: '' },
  nodes: { type: Array, default: () => [] },
})

const resourceTypes = [
  { value: 'video', label: '视频' },
  { value: 'exercise', label: '练习' },
  { value: 'article', label: '文章' },
  { value: 'quiz', label: '测验' },
  { value: 'document', label: '文档' },
  { value: 'link', label: '链接' },
  { value: 'ai_prompt', label: 'AI 提示' },
]

const statuses = [
  { value: 'draft', label: '草稿' },
  { value: 'published', label: '已上线' },
  { value: 'offline', label: '已下线' },
]

const loading = ref(false)
const resources = ref([])
const selectedResourceIds = ref([])
const selectedNodeIds = ref([])
const tagText = ref('')
const { showToast } = useToast()

const filters = reactive({
  q: '',
  type: '',
  status: '',
})

const form = reactive({
  title: '',
  type: 'video',
  url: '',
  description: '',
  difficulty: 1,
  estimated_time: 0,
  status: 'published',
  source: '',
  node_ids: [],
})

watch(() => props.courseId, () => {
  clearSelection()
  fetchResources()
}, { immediate: true })

async function fetchResources() {
  if (!props.courseId) {
    resources.value = []
    return
  }
  loading.value = true
  try {
    resources.value = await resourceApi.list({
      course_id: props.courseId,
      q: filters.q || undefined,
      type: filters.type || undefined,
      status: filters.status || undefined,
    })
  } catch {
    resources.value = []
  } finally {
    loading.value = false
  }
}

async function createResource() {
  if (!props.courseId || !form.title) return
  loading.value = true
  try {
    await resourceApi.create({
      ...form,
      course_id: props.courseId,
      tags: tagText.value,
    })
    resetForm()
    await fetchResources()
  } catch (err) {
    showToast(err.normalizedMessage || '创建资源失败', 'error')
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.title = ''
  form.type = 'video'
  form.url = ''
  form.description = ''
  form.difficulty = 1
  form.estimated_time = 0
  form.status = 'published'
  form.source = ''
  form.node_ids = []
  tagText.value = ''
}

function toggleResource(id) {
  const set = new Set(selectedResourceIds.value)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  selectedResourceIds.value = [...set]
}

function clearSelection() {
  selectedResourceIds.value = []
  selectedNodeIds.value = []
}

async function updateStatus(resource, status) {
  try {
    await resourceApi.update(resource.id, { status })
    resource.status = status
  } catch (err) {
    showToast(err.normalizedMessage || '更新状态失败', 'error')
  }
}

async function deleteResource(resource) {
  if (!confirm('确认删除资源：' + resource.title + '？')) return
  try {
    await resourceApi.delete(resource.id)
    resources.value = resources.value.filter(item => item.id !== resource.id)
    selectedResourceIds.value = selectedResourceIds.value.filter(id => id !== resource.id)
  } catch (err) {
    showToast(err.normalizedMessage || '删除资源失败', 'error')
  }
}

async function batchAttach() {
  try {
    await resourceApi.batchAttach(selectedResourceIds.value, selectedNodeIds.value)
    await fetchResources()
  } catch (err) {
    showToast(err.normalizedMessage || '批量挂载失败', 'error')
  }
}

async function batchPublish() {
  try {
    await resourceApi.batchStatus(selectedResourceIds.value, 'published')
    await fetchResources()
  } catch (err) {
    showToast(err.normalizedMessage || '批量上线失败', 'error')
  }
}

async function migrateLegacy() {
  if (!confirm('将当前课程知识点中的旧视频和习题字段迁移为独立资源，是否继续？')) return
  loading.value = true
  try {
    const result = await resourceApi.migrateLegacy(props.courseId)
    await fetchResources()
    showToast(`迁移完成：${result.nodes || 0} 个知识点，${result.resources || 0} 个资源`, 'success')
  } catch (err) {
    showToast(err.normalizedMessage || '迁移失败', 'error')
  } finally {
    loading.value = false
  }
}

function typeLabel(value) {
  return resourceTypes.find(item => item.value === value)?.label || value || '资源'
}

function statusLabel(value) {
  return statuses.find(item => item.value === value)?.label || '草稿'
}

function boundNodeNames(resource) {
  const names = (resource.knowledge_nodes || []).map(node => node.name).filter(Boolean)
  return names.length ? names.join('、') : '未挂载'
}
</script>
