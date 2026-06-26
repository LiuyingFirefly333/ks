<template>
  <div class="graph-editor-panel">
    <div class="node-detail-header">
      <div>
        <div class="panel-eyebrow">图谱编辑器</div>
        <h3>{{ title }}</h3>
      </div>
      <button class="icon-button" @click="$emit('close')" title="关闭">×</button>
    </div>

    <div class="node-detail-body graph-editor-body">
      <section v-if="node" class="editor-section">
        <div class="section-head compact">
          <h4>知识点属性</h4>
          <button class="danger small" @click="$emit('delete-node', node)">删除</button>
        </div>

        <div class="form-row">
          <label>名称</label>
          <input v-model.trim="nodeForm.name" />
        </div>
        <div class="form-row">
          <label>分类</label>
          <input v-model.trim="nodeForm.category" />
        </div>
        <div class="form-row two-cols">
          <div>
            <label>难度</label>
            <input v-model.number="nodeForm.difficulty" type="number" min="1" max="5" />
          </div>
          <div>
            <label>预计时长</label>
            <input v-model.number="nodeForm.estimated_time" type="number" min="0" />
          </div>
        </div>
        <div class="form-row">
          <label>描述</label>
          <textarea v-model="nodeForm.description" rows="3"></textarea>
        </div>
        <div class="form-row">
          <label>视频资源</label>
          <textarea v-model="nodeForm.videoText" rows="2"></textarea>
        </div>
        <div class="form-row">
          <label>习题资源</label>
          <textarea v-model="nodeForm.exerciseText" rows="2"></textarea>
        </div>
        <div class="form-actions">
          <button @click="saveNode" :disabled="!nodeForm.name">保存属性</button>
          <button class="secondary" @click="$emit('start-relation', node.id)">设为源点</button>
        </div>
      </section>

      <section v-if="link" class="editor-section relation-editor-section">
        <div class="section-head compact">
          <h4>关系属性</h4>
          <button class="danger small" @click="$emit('delete-link', link)">删除</button>
        </div>

        <div class="form-row">
          <label>源知识点</label>
          <select v-model="linkForm.source">
            <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>目标知识点</label>
          <select v-model="linkForm.target">
            <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
          </select>
        </div>
        <div class="form-row two-cols">
          <div>
            <label>类型</label>
            <select v-model="linkForm.type">
              <option value="PREREQUISITE">前置知识</option>
              <option value="RELATED_TO">相关概念</option>
            </select>
          </div>
          <div>
            <label>权重</label>
            <input v-model.number="linkForm.weight" type="number" min="0.1" max="5" step="0.1" />
          </div>
        </div>
        <button
          @click="saveLink"
          :disabled="!linkForm.source || !linkForm.target || linkForm.source === linkForm.target"
        >
          保存关系
        </button>
      </section>

      <section class="editor-section">
        <div class="section-head compact">
          <h4>新建关系</h4>
          <span v-if="relationSourceName" class="cat-tag">{{ relationSourceName }}</span>
        </div>
        <div class="form-row">
          <label>源知识点</label>
          <select v-model="relationForm.source">
            <option value="">请选择</option>
            <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>目标知识点</label>
          <select v-model="relationForm.target">
            <option value="">请选择</option>
            <option v-for="n in nodes" :key="n.id" :value="n.id">{{ n.name }}</option>
          </select>
        </div>
        <div class="form-row two-cols">
          <div>
            <label>类型</label>
            <select v-model="relationForm.type">
              <option value="PREREQUISITE">前置知识</option>
              <option value="RELATED_TO">相关概念</option>
            </select>
          </div>
          <div>
            <label>权重</label>
            <input v-model.number="relationForm.weight" type="number" min="0.1" max="5" step="0.1" />
          </div>
        </div>
        <div class="form-actions">
          <button
            @click="createRelation"
            :disabled="!relationForm.source || !relationForm.target || relationForm.source === relationForm.target"
          >
            建立关系
          </button>
          <button v-if="relationSourceId" class="secondary" @click="$emit('cancel-relation')">取消源点</button>
        </div>
      </section>

      <section class="editor-section">
        <div class="section-head compact">
          <h4>批量操作</h4>
          <span class="cat-tag">{{ selectedNodeIds.length }} 项</span>
        </div>
        <div class="form-row two-cols">
          <div>
            <label>统一分类</label>
            <input v-model.trim="batchForm.category" />
          </div>
          <div>
            <label>统一难度</label>
            <input v-model.number="batchForm.difficulty" type="number" min="1" max="5" />
          </div>
        </div>
        <div class="form-actions">
          <button class="secondary" @click="$emit('toggle-batch')">{{ batchMode ? '退出多选' : '开启多选' }}</button>
          <button @click="batchUpdate" :disabled="!selectedNodeIds.length || (!batchForm.category && !batchForm.difficulty)">应用</button>
        </div>
        <div class="form-actions">
          <button class="secondary" @click="$emit('clear-selection')" :disabled="!selectedNodeIds.length">清空选择</button>
          <button class="danger" @click="$emit('batch-delete')" :disabled="!selectedNodeIds.length">批量删除</button>
        </div>
      </section>

      <section class="editor-section">
        <h4>新增知识点</h4>
        <div class="form-row">
          <label>名称</label>
          <input v-model.trim="createForm.name" />
        </div>
        <div class="form-row">
          <label>分类</label>
          <input v-model.trim="createForm.category" />
        </div>
        <div class="form-row two-cols">
          <div>
            <label>难度</label>
            <input v-model.number="createForm.difficulty" type="number" min="1" max="5" />
          </div>
          <div>
            <label>预计时长</label>
            <input v-model.number="createForm.estimated_time" type="number" min="0" />
          </div>
        </div>
        <div class="form-row">
          <label>描述</label>
          <textarea v-model="createForm.description" rows="2"></textarea>
        </div>
        <button @click="createNode" :disabled="!createForm.name">创建知识点</button>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  node: { type: Object, default: null },
  link: { type: Object, default: null },
  nodes: { type: Array, default: () => [] },
  selectedNodeIds: { type: Array, default: () => [] },
  relationSourceId: { type: String, default: '' },
  relationDraftType: { type: String, default: 'PREREQUISITE' },
  relationDraftWeight: { type: Number, default: 1 },
  batchMode: { type: Boolean, default: false },
})

const emit = defineEmits([
  'close',
  'save-node',
  'delete-node',
  'start-relation',
  'cancel-relation',
  'create-relation',
  'save-link',
  'delete-link',
  'update-relation-draft',
  'toggle-batch',
  'clear-selection',
  'batch-update',
  'batch-delete',
  'create-node',
])

const nodeForm = reactive({
  name: '',
  category: '',
  difficulty: 1,
  estimated_time: 0,
  description: '',
  videoText: '',
  exerciseText: '',
})

const linkForm = reactive({
  source: '',
  target: '',
  type: 'PREREQUISITE',
  weight: 1,
})

const relationForm = reactive({
  source: '',
  target: '',
  type: 'PREREQUISITE',
  weight: 1,
})

const batchForm = reactive({
  category: '',
  difficulty: null,
})

const createForm = reactive({
  name: '',
  category: '',
  difficulty: 1,
  estimated_time: 0,
  description: '',
})

const title = computed(() => {
  if (props.link) return '关系维护'
  if (props.node) return props.node.name || '知识点维护'
  return '在线维护'
})

const relationSourceName = computed(() => {
  const node = props.nodes.find(n => n.id === relationForm.source)
  return node?.name || ''
})

watch(() => props.node, node => {
  nodeForm.name = node?.name || ''
  nodeForm.category = node?.category || ''
  nodeForm.difficulty = Number(node?.difficulty || 1)
  nodeForm.estimated_time = Number(node?.estimated_time || 0)
  nodeForm.description = node?.description || ''
  nodeForm.videoText = (node?.video_urls || []).join('\n')
  nodeForm.exerciseText = (node?.exercises || []).join('\n')
}, { immediate: true })

watch(() => props.link, link => {
  linkForm.source = normalizeId(link?.source)
  linkForm.target = normalizeId(link?.target)
  linkForm.type = link?.type || 'PREREQUISITE'
  linkForm.weight = Number(link?.weight || 1)
}, { immediate: true })

watch(() => props.relationSourceId, source => {
  if (source) relationForm.source = source
}, { immediate: true })

watch(() => props.relationDraftType, type => {
  if (type) relationForm.type = type
}, { immediate: true })

watch(() => props.relationDraftWeight, weight => {
  relationForm.weight = Number(weight || 1)
}, { immediate: true })

watch(() => [relationForm.type, relationForm.weight], () => {
  emit('update-relation-draft', {
    type: relationForm.type,
    weight: Number(relationForm.weight || 1),
  })
})

function normalizeId(value) {
  return typeof value === 'object' ? value?.id || '' : value || ''
}

function splitLines(value) {
  return String(value || '')
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
}

function saveNode() {
  emit('save-node', props.node, {
    name: nodeForm.name,
    category: nodeForm.category || '未分类',
    difficulty: Number(nodeForm.difficulty || 1),
    estimated_time: Number(nodeForm.estimated_time || 0),
    description: nodeForm.description,
    video_urls: splitLines(nodeForm.videoText),
    exercises: splitLines(nodeForm.exerciseText),
  })
}

function saveLink() {
  emit('save-link', props.link, {
    source: linkForm.source,
    target: linkForm.target,
    type: linkForm.type,
    weight: Number(linkForm.weight || 1),
  })
}

function createRelation() {
  emit('create-relation', {
    source: relationForm.source,
    target: relationForm.target,
    type: relationForm.type,
    weight: Number(relationForm.weight || 1),
  })
}

function batchUpdate() {
  const payload = {}
  if (batchForm.category) payload.category = batchForm.category
  if (batchForm.difficulty) payload.difficulty = Number(batchForm.difficulty)
  emit('batch-update', payload)
}

function createNode() {
  emit('create-node', {
    name: createForm.name,
    category: createForm.category || '未分类',
    difficulty: Number(createForm.difficulty || 1),
    estimated_time: Number(createForm.estimated_time || 0),
    description: createForm.description,
  })
  createForm.name = ''
  createForm.category = ''
  createForm.difficulty = 1
  createForm.estimated_time = 0
  createForm.description = ''
}
</script>
