<template>
  <div>
    <div v-if="hotNodes.length" class="admin-section">
      <h4>热点知识点 TOP 10</h4>
      <div v-for="h in hotNodes" :key="h.node_id" class="admin-hot-row">
        <span class="admin-hot-name" @click="$emit('locate', h.node_id)">{{ h.name }}</span>
        <span class="admin-hot-meta">{{ h.assess_count }} 次 · 均分 {{ h.avg_score }}</span>
      </div>
    </div>

    <div class="admin-section">
      <div class="section-head">
        <h4>知识库运维</h4>
        <div class="admin-section-actions">
          <button class="secondary small" @click="$emit('create-backup')" :disabled="opsLoading">版本备份</button>
          <button class="secondary small" @click="$emit('clean-graph-data')" :disabled="opsLoading">数据清洗</button>
          <button class="secondary small" @click="$emit('cleanup-redundant')" :disabled="opsLoading">冗余清理</button>
          <button class="secondary small" @click="$emit('check-conflicts')" :disabled="conflictLoading">冲突检测</button>
        </div>
      </div>
      <div v-if="opsMessage" class="inline-hint">{{ opsMessage }}</div>

      <div class="ops-grid">
        <div class="ops-card">
          <h5>版本备份</h5>
          <div v-if="!backups.length" class="empty-state compact">暂无备份</div>
          <div v-for="backup in backups.slice(0, 4)" :key="backup.id" class="backup-row">
            <span>{{ backup.label || '知识库备份' }}</span>
            <small>{{ formatDate(backup.created_at) }} · {{ backup.node_count || 0 }} 节点 · {{ backup.relation_count || 0 }} 关系</small>
          </div>
        </div>

        <div class="ops-card">
          <h5>增量更新</h5>
          <div class="form-row">
            <label>目标课程</label>
            <select v-model="localCourseId">
              <option value="">选择课程</option>
              <option v-for="course in courses" :key="course.id" :value="course.id">{{ course.name }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>JSON 数据</label>
            <textarea v-model.trim="localIncrementalText" rows="6" placeholder='{"nodes":[{"name":"知识点A"}],"relations":[]}'></textarea>
          </div>
          <button class="full-width" @click="$emit('apply-incremental-update')" :disabled="opsLoading || !localCourseId || !localIncrementalText">应用增量更新</button>
        </div>
      </div>

      <div v-if="conflictLoading" class="loading-spinner"></div>
      <div v-if="!conflictLoading && conflicts.length === 0" class="empty-state compact">暂未发现冲突</div>
      <div v-for="(c, i) in conflicts" :key="i" class="conflict-item" :class="c.type">
        <span class="conflict-badge">{{ conflictLabel(c) }}</span>
        <span class="conflict-name">{{ c.name || c.node_id || c.source_id }}</span>
        <span class="conflict-detail">{{ c.detail }}</span>
        <button class="secondary small" @click="$emit('fix-conflict', c)" :disabled="opsLoading || !c.fixable">修复</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  hotNodes: { type: Array, default: () => [] },
  backups: { type: Array, default: () => [] },
  courses: { type: Array, default: () => [] },
  conflicts: { type: Array, default: () => [] },
  incrementalCourseId: { type: String, default: '' },
  incrementalText: { type: String, default: '' },
  conflictLoading: { type: Boolean, default: false },
  opsLoading: { type: Boolean, default: false },
  opsMessage: { type: String, default: '' },
  formatDate: { type: Function, required: true },
  conflictLabel: { type: Function, required: true },
})

const emit = defineEmits([
  'locate',
  'create-backup',
  'clean-graph-data',
  'cleanup-redundant',
  'check-conflicts',
  'fix-conflict',
  'apply-incremental-update',
  'update:incrementalCourseId',
  'update:incrementalText',
])

const localCourseId = computed({
  get: () => props.incrementalCourseId,
  set: value => emit('update:incrementalCourseId', value),
})

const localIncrementalText = computed({
  get: () => props.incrementalText,
  set: value => emit('update:incrementalText', value),
})
</script>
