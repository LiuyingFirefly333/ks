import { ref } from 'vue'

import { analyticsApi } from '../api/index.js'

export function useMastery(userId, currentCourseId) {
  const masteryMap = ref({})
  const masteredIds = ref([])

  function scoreLevel(score) {
    if (score >= 85) return 'proficient'
    if (score >= 60) return 'fair'
    if (score > 0) return 'weak'
    return 'unlearned'
  }

  async function fetchMastery() {
    if (!userId.value || !currentCourseId.value) return
    try {
      const data = await analyticsApi.calcMastery(userId.value, currentCourseId.value)
      const map = {}
      for (const n of (data.nodes || [])) map[n.node_id] = { score: n.score, level: n.level }
      masteryMap.value = map
      masteredIds.value = Object.entries(map).filter(([, v]) => v.score >= 70).map(([id]) => id)
    } catch {
      masteryMap.value = {}
      masteredIds.value = []
    }
  }

  function updateLocalMastery(nodeId, score) {
    const level = scoreLevel(score)
    masteryMap.value = {
      ...masteryMap.value,
      [nodeId]: { ...(masteryMap.value[nodeId] || {}), score, level, manual_score: score },
    }
    return level
  }

  return {
    masteryMap,
    masteredIds,
    fetchMastery,
    updateLocalMastery,
  }
}
