import { ref } from 'vue'

import { analyticsApi, classroomApi } from '../api/index.js'

export function useClassroomHeatmap(user, currentCourseId, fetchGraph) {
  const classes = ref([])
  const currentClassId = ref('')
  const heatmapData = ref([])
  const heatmapMode = ref(false)

  async function fetchClasses() {
    if (user.value?.role !== 'teacher') return
    try {
      classes.value = await classroomApi.listClasses(user.value.id)
    } catch {
      classes.value = []
    }
  }

  async function fetchHeatmap() {
    if (!currentClassId.value || !currentCourseId.value) return
    try {
      const data = await analyticsApi.classHeatmap(currentClassId.value, currentCourseId.value)
      heatmapData.value = data.nodes || []
      await fetchGraph()
    } catch {
      heatmapData.value = []
    }
  }

  async function onClassChange() {
    if (heatmapMode.value) await fetchHeatmap()
  }

  async function toggleHeatmap() {
    heatmapMode.value = !heatmapMode.value
    if (heatmapMode.value && currentClassId.value) await fetchHeatmap()
    else {
      heatmapData.value = []
      await fetchGraph()
    }
  }

  return {
    classes,
    currentClassId,
    heatmapData,
    heatmapMode,
    fetchClasses,
    fetchHeatmap,
    onClassChange,
    toggleHeatmap,
  }
}
