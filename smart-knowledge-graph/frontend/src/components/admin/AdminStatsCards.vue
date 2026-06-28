<template>
  <div class="admin-stats">
    <div v-for="item in items" :key="item.key" class="stat-card">
      <div class="stat-num">{{ item.value }}</div>
      <div class="stat-label">{{ item.label }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stats: { type: Object, default: () => ({}) },
})

const items = computed(() => [
  { key: 'nodes', label: '知识点', value: props.stats.total_nodes || 0 },
  { key: 'students', label: '学生', value: props.stats.total_students || 0 },
  { key: 'teachers', label: '教师', value: props.stats.total_teachers || 0 },
  { key: 'admins', label: '管理员', value: props.stats.total_admins || 0 },
  { key: 'classes', label: '班级', value: props.stats.total_classes || 0 },
])
</script>
