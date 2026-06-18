<template>
  <div v-if="node" class="node-detail-panel">
    <div class="node-detail-header">
      <h3>{{ node.name }}</h3>
      <button class="close" @click="$emit('close')">&times;</button>
    </div>
    <div class="node-detail-body">
      <div class="field">
        <div class="label">分类</div>
        <div class="value">{{ node.category }}</div>
      </div>
      <div class="field">
        <div class="label">难度</div>
        <div class="diff-dots">
          <span
            v-for="i in 5"
            :key="i"
            class="dot"
            :class="i <= (node.difficulty || 1) ? 'fill' : 'empty'"
          ></span>
        </div>
      </div>
      <div class="field">
        <div class="label">描述</div>
        <div class="value">{{ node.description || '暂无描述' }}</div>
      </div>
      <div class="field" v-if="neighbors.length">
        <div class="label">关联知识点 ({{ neighbors.length }})</div>
        <div v-for="nb in neighbors" :key="nb.node.id" class="node-item" @click="$emit('locate', nb.node)">
          <span>{{ nb.node.name }}</span>
          <span class="cat-tag">{{ nb.relation.type || '关联' }}</span>
        </div>
      </div>
      <div class="form-actions" style="margin-top:12px">
        <button class="ghost" style="flex:1" @click="$emit('show-roadmap', node.id)">查看学习路线</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { graphApi } from '../api/index.js'

const props = defineProps({
  node: { type: Object, default: null },
})
const emit = defineEmits(['close', 'locate', 'show-roadmap'])

const neighbors = ref([])

watch(() => props.node, async (val) => {
  if (val && val.id) {
    try {
      const data = await graphApi.getNeighbors(val.id)
      neighbors.value = data
    } catch {
      neighbors.value = []
    }
  } else {
    neighbors.value = []
  }
}, { immediate: true })
</script>
