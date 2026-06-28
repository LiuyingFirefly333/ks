import { computed, ref } from 'vue'

import { graphApi } from '../api/index.js'

export function useGraphState(currentCourseId, userId) {
  const nodes = ref([])
  const links = ref([])
  const categories = ref([])
  const selectedCategory = ref('')
  const highlightedPath = ref([])
  const highlightedPaths = ref([])
  const searchNodeId = ref(null)
  const graphPositions = ref({})
  const graphViewports = ref({})
  const graphLayoutModes = ref({})

  const currentGraphViewport = computed(() => graphViewports.value[currentCourseId.value || 'global'] || null)
  const currentGraphLayoutMode = computed(() => graphLayoutModes.value[currentCourseId.value || 'global'] || 'dagre')

  function positionStorageKey() {
    return `kg:positions:${currentCourseId.value || 'global'}`
  }

  function viewportStorageKey() {
    return currentCourseId.value || 'global'
  }

  function loadGraphPositions() {
    try {
      graphPositions.value = JSON.parse(localStorage.getItem(positionStorageKey()) || '{}')
    } catch {
      graphPositions.value = {}
    }
  }

  function saveGraphPositions() {
    localStorage.setItem(positionStorageKey(), JSON.stringify(graphPositions.value))
  }

  function onGraphViewportChange(viewport) {
    if (!viewport) return
    const x = Number(viewport.x)
    const y = Number(viewport.y)
    const k = Number(viewport.k)
    if (![x, y, k].every(Number.isFinite)) return
    const key = viewportStorageKey()
    if (viewport.layoutMode) {
      graphLayoutModes.value = {
        ...graphLayoutModes.value,
        [key]: viewport.layoutMode === 'force' ? 'force' : 'dagre',
      }
    }
    graphViewports.value = {
      ...graphViewports.value,
      [key]: { x, y, k, layoutMode: viewport.layoutMode },
    }
  }

  function onGraphLayoutChange(mode) {
    const key = viewportStorageKey()
    graphLayoutModes.value = { ...graphLayoutModes.value, [key]: mode === 'force' ? 'force' : 'dagre' }
    const { [key]: _removed, ...rest } = graphViewports.value
    graphViewports.value = rest
  }

  function onNodePositionChange(position) {
    graphPositions.value = {
      ...graphPositions.value,
      [position.id]: {
        x: Math.round(position.x),
        y: Math.round(position.y),
      },
    }
    saveGraphPositions()
  }

  async function fetchGraph() {
    if (!currentCourseId.value) {
      nodes.value = []
      links.value = []
      return
    }
    const data = await graphApi.getGraph(selectedCategory.value || undefined, currentCourseId.value, userId.value)
    nodes.value = data.nodes || []
    links.value = data.links || []
  }

  async function fetchCategories() {
    if (!currentCourseId.value) {
      categories.value = []
      return
    }
    categories.value = await graphApi.getCategories(currentCourseId.value)
  }

  function clearPath() {
    highlightedPath.value = []
    highlightedPaths.value = []
  }

  function setPath(pathNodes, pathGroups = []) {
    highlightedPath.value = pathNodes.map(n => n.id)
    highlightedPaths.value = pathGroups.map(group => ({
      ...group,
      nodes: (group.path || []).map(node => node.id),
    }))
  }

  function removeNodePosition(nodeId) {
    delete graphPositions.value[nodeId]
    saveGraphPositions()
  }

  return {
    nodes,
    links,
    categories,
    selectedCategory,
    highlightedPath,
    highlightedPaths,
    searchNodeId,
    graphPositions,
    graphViewports,
    graphLayoutModes,
    currentGraphViewport,
    currentGraphLayoutMode,
    loadGraphPositions,
    saveGraphPositions,
    onGraphViewportChange,
    onGraphLayoutChange,
    onNodePositionChange,
    fetchGraph,
    fetchCategories,
    clearPath,
    setPath,
    removeNodePosition,
  }
}
