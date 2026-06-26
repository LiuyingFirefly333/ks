<template>
  <div ref="container" class="graph-wrapper">
    <div class="graph-toolbar-top graph-layout-toolbar">
      <div class="graph-mode-switch">
        <button :class="{ active: layoutMode === 'force' }" @click="setLayout('force')" title="力导向布局">
          力导向
        </button>
        <button :class="{ active: layoutMode === 'dagre' }" @click="setLayout('dagre')" title="Dagre 分层布局">
          分层
        </button>
      </div>
      <span class="toolbar-sep"></span>
      <span class="graph-stat-chip">{{ props.nodes.length }} 点</span>
      <span class="graph-stat-chip">{{ props.links.length }} 边</span>
      <span class="toolbar-sep"></span>
      <button @click="fitToScreen" title="适应画布">适应</button>
      <button @click="exportSVG" title="导出 SVG 图片">SVG</button>
      <button @click="exportJSON" title="导出 JSON 数据">JSON</button>
      <button @click="exportCSV" title="导出 CSV 表格">CSV</button>
    </div>

    <div class="graph-mode-label">
      <strong>{{ layoutTitle }}</strong>
      <span>{{ layoutHint }}</span>
    </div>

    <svg ref="svgEl" class="graph-svg"></svg>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import dagreModule from 'dagre'

const dagre = dagreModule.default || dagreModule

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  links: { type: Array, default: () => [] },
  highlightedPath: { type: Array, default: () => [] },
  searchNodeId: { type: String, default: null },
  selectedNodeId: { type: String, default: null },
  masteryMap: { type: Object, default: () => ({}) },
  heatmapData: { type: Array, default: () => [] },
  heatmapMode: { type: Boolean, default: false },
  editable: { type: Boolean, default: false },
  editMode: { type: Boolean, default: false },
  selectedLinkKey: { type: String, default: '' },
  selectedNodeIds: { type: Array, default: () => [] },
  relationSourceId: { type: String, default: '' },
  nodePositions: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['select-node', 'select-link', 'node-position-change'])

const container = ref(null)
const svgEl = ref(null)
const layoutMode = ref('dagre')

let simulation = null
let svg = null
let g = null
let zoomBehavior = null
let resizeObserver = null
let currentNodes = []
let currentLinks = []

const NODE_W = 172
const NODE_H = 58
const MIN_ZOOM = 0.18
const MAX_ZOOM = 3.5
const VIEW_PADDING = 76

const layoutTitle = computed(() => layoutMode.value === 'dagre' ? 'Dagre 分层视图' : '力导向关系视图')
const layoutHint = computed(() => layoutMode.value === 'dagre'
  ? '适合章节依赖、学习路径和前置关系梳理'
  : '适合观察跨章节关联、知识团簇和网状关系')

const CATEGORY_COLORS = {
  '高等数学-基础': '#2563eb',
  '高等数学-极限': '#16a34a',
  '高等数学-导数': '#f59e0b',
  '高等数学-积分': '#0891b2',
  '高等数学-微分方程': '#dc2626',
}

const MASTERY_COLORS = {
  proficient: '#16a34a',
  fair: '#f59e0b',
  weak: '#f97316',
  unlearned: '#94a3b8',
}

const HEAT_COLORS = ['#16a34a', '#84cc16', '#f59e0b', '#f97316', '#ef4444', '#b91c1c']

function getHeatColor(avgScore) {
  if (avgScore >= 85) return HEAT_COLORS[0]
  if (avgScore >= 70) return HEAT_COLORS[1]
  if (avgScore >= 55) return HEAT_COLORS[2]
  if (avgScore >= 40) return HEAT_COLORS[3]
  if (avgScore > 0) return HEAT_COLORS[4]
  return '#94a3b8'
}

function hashColor(key) {
  const palette = ['#2563eb', '#0f766e', '#7c3aed', '#db2777', '#0891b2', '#ea580c', '#475569']
  const value = String(key || '未分类')
  let hash = 0
  for (let i = 0; i < value.length; i++) hash = (hash + value.charCodeAt(i) * (i + 1)) % palette.length
  return palette[hash]
}

function getColor(node) {
  if (props.heatmapMode) {
    const heat = props.heatmapData.find(item => item.node_id === node.id)
    if (heat) return getHeatColor(heat.avg_score)
  }

  const mastery = props.masteryMap[node.id]
  if (mastery) return MASTERY_COLORS[mastery.level] || hashColor(node.category)

  return CATEGORY_COLORS[node.category] || hashColor(node.category)
}

function getNodeState(node) {
  if (props.relationSourceId === node.id) return 'relation-source'
  if (props.selectedNodeIds.includes(node.id)) return 'batch-selected'
  if (node.id === props.selectedNodeId) return 'selected'
  if (node.id === props.searchNodeId) return 'searched'
  if (isInPath(node.id)) return 'path'
  return 'normal'
}

function isInPath(nodeId) {
  return props.highlightedPath.includes(nodeId)
}

function pathEdgeSet() {
  const set = new Set()
  for (let i = 0; i < props.highlightedPath.length - 1; i++) {
    set.add(`${props.highlightedPath[i]}->${props.highlightedPath[i + 1]}`)
  }
  return set
}

function isPathLink(link, pathSet = pathEdgeSet()) {
  const source = normalizeId(link.source)
  const target = normalizeId(link.target)
  return pathSet.has(`${source}->${target}`)
}

function linkKey(link) {
  return `${normalizeId(link.source)}->${normalizeId(link.target)}:${link.type || 'RELATED_TO'}`
}

function isSelectedLink(link) {
  return props.selectedLinkKey && props.selectedLinkKey === linkKey(link)
}

function normalizeId(value) {
  return typeof value === 'object' ? value.id : value
}

function displayCategory(category) {
  return String(category || '未分类').split('-').pop()
}

function shortText(text, limit = 12) {
  const value = String(text || '')
  return value.length > limit ? `${value.slice(0, limit)}...` : value
}

function relationLabel(type) {
  if (type === 'RELATED_TO') return '相关'
  if (type === 'PREREQUISITE') return '前置'
  return type || '关系'
}

function setLayout(mode) {
  if (layoutMode.value === mode) return
  layoutMode.value = mode
  nextTick(() => initGraph())
}

function buildGraphData() {
  const nodeData = props.nodes.map(node => ({ ...node }))
  const nodeIds = new Set(nodeData.map(node => node.id))
  const linkData = props.links
    .map(link => ({ ...link, source: normalizeId(link.source), target: normalizeId(link.target) }))
    .filter(link => nodeIds.has(link.source) && nodeIds.has(link.target))
  return { nodeData, linkData }
}

function applyStoredPositions(nodes) {
  nodes.forEach(node => {
    const saved = props.nodePositions?.[node.id]
    if (!saved) return
    const x = Number(saved.x)
    const y = Number(saved.y)
    if (Number.isFinite(x) && Number.isFinite(y)) {
      node.x = x
      node.y = y
      if (props.editMode) {
        node.fx = x
        node.fy = y
      }
    }
  })
}

function layoutWithDagre(nodes, links) {
  const graph = new dagre.graphlib.Graph({ multigraph: true })
  graph.setGraph({
    rankdir: 'LR',
    align: 'UL',
    nodesep: 36,
    ranksep: 118,
    edgesep: 18,
    marginx: VIEW_PADDING,
    marginy: VIEW_PADDING,
    ranker: 'network-simplex',
    acyclicer: 'greedy',
  })
  graph.setDefaultEdgeLabel(() => ({}))

  nodes.forEach(node => graph.setNode(node.id, {
    width: NODE_W + Math.min(String(node.name || '').length * 3, 42),
    height: NODE_H,
  }))
  links.forEach((link, index) => graph.setEdge(link.source, link.target, {}, `${link.source}-${link.target}-${index}`))

  dagre.layout(graph)

  nodes.forEach(node => {
    const dagreNode = graph.node(node.id)
    if (!dagreNode) return
    node.x = dagreNode.x
    node.y = dagreNode.y
    node.vx = 0
    node.vy = 0
  })
}

function nodeDepths(nodes, links) {
  const ids = new Set(nodes.map(node => node.id))
  const incoming = new Map(nodes.map(node => [node.id, 0]))
  const outgoing = new Map(nodes.map(node => [node.id, []]))

  links.forEach(link => {
    if (!ids.has(link.source) || !ids.has(link.target)) return
    incoming.set(link.target, (incoming.get(link.target) || 0) + 1)
    outgoing.get(link.source)?.push(link.target)
  })

  const queue = nodes.filter(node => !incoming.get(node.id)).map(node => node.id)
  const depths = new Map(nodes.map(node => [node.id, 0]))
  const fallbackIds = nodes.map(node => node.id)
  while (queue.length) {
    const id = queue.shift()
    for (const target of outgoing.get(id) || []) {
      depths.set(target, Math.max(depths.get(target) || 0, (depths.get(id) || 0) + 1))
      incoming.set(target, (incoming.get(target) || 0) - 1)
      if (incoming.get(target) === 0) queue.push(target)
    }
  }

  fallbackIds.forEach((id, index) => {
    if (!depths.has(id)) depths.set(id, index % 5)
  })
  return depths
}

function categoryLanes(nodes) {
  const categories = [...new Set(nodes.map(node => node.category || '未分类'))]
  return new Map(categories.map((category, index) => [category, index]))
}

async function initGraph() {
  if (!container.value || !svgEl.value) return
  const rect = container.value.getBoundingClientRect()
  const width = Math.max(rect.width, 320)
  const height = Math.max(rect.height, 260)

  if (simulation) {
    simulation.stop()
    simulation = null
  }

  svg = d3.select(svgEl.value)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('role', 'img')
    .attr('aria-label', '知识图谱可视化')

  svg.selectAll('*').remove()

  const defs = svg.append('defs')
  createArrow(defs, 'arrow-prerequisite', '#64748b')
  createArrow(defs, 'arrow-related', '#94a3b8')
  createArrow(defs, 'arrow-path', '#ef4444')
  createGlow(defs)

  g = svg.append('g').attr('class', 'graph-layer')
  const linkLayer = g.append('g').attr('class', 'graph-link-layer')
  const labelLayer = g.append('g').attr('class', 'graph-edge-label-layer')
  const nodeLayer = g.append('g').attr('class', 'graph-node-layer')

  zoomBehavior = d3.zoom()
    .scaleExtent([MIN_ZOOM, MAX_ZOOM])
    .filter(event => !event.ctrlKey || event.type === 'wheel')
    .on('zoom', event => g.attr('transform', event.transform))
  svg.call(zoomBehavior)
  svg.on('dblclick.zoom', null)

  const { nodeData, linkData } = buildGraphData()
  currentNodes = nodeData
  currentLinks = linkData
  if (!nodeData.length) return

  if (layoutMode.value === 'dagre') {
    layoutWithDagre(nodeData, linkData)
  } else {
    seedForceLayout(nodeData, linkData, width, height)
  }
  applyStoredPositions(nodeData)

  const pathSet = pathEdgeSet()
  const links = linkLayer.selectAll('path')
    .data(linkData, linkKey)
    .join('path')
    .attr('class', d => `graph-link ${isPathLink(d, pathSet) ? 'is-path' : ''} ${isSelectedLink(d) ? 'is-selected' : ''}`)
    .attr('cursor', props.editable ? 'pointer' : null)
    .attr('stroke', d => {
      if (isSelectedLink(d)) return '#0f172a'
      return isPathLink(d, pathSet) ? '#ef4444' : (d.type === 'RELATED_TO' ? '#94a3b8' : '#64748b')
    })
    .attr('stroke-width', d => isSelectedLink(d) ? 4 : (isPathLink(d, pathSet) ? 3 : Math.max(1.4, (d.weight || 1) * 1.2)))
    .attr('stroke-opacity', d => isPathLink(d, pathSet) ? 0.95 : 0.42)
    .attr('stroke-dasharray', d => d.type === 'RELATED_TO' ? '6 5' : null)
    .attr('marker-end', d => {
      if (isPathLink(d, pathSet)) return 'url(#arrow-path)'
      return d.type === 'RELATED_TO' ? 'url(#arrow-related)' : 'url(#arrow-prerequisite)'
    })
    .on('click', (event, link) => {
      if (!props.editable) return
      event.stopPropagation()
      emit('select-link', { ...link, key: linkKey(link) })
    })

  const edgeLabels = labelLayer.selectAll('text')
    .data(linkData.filter(link => isPathLink(link, pathSet) || layoutMode.value === 'dagre'))
    .join('text')
    .attr('class', 'graph-edge-label')
    .text(d => relationLabel(d.type))
    .attr('fill', d => isPathLink(d, pathSet) ? '#dc2626' : '#64748b')

  const nodes = nodeLayer.selectAll('g')
    .data(nodeData)
    .join('g')
    .attr('class', d => `graph-node-card state-${getNodeState(d)}`)
    .attr('cursor', props.editMode ? 'move' : 'pointer')
    .on('click', (event, node) => {
      if (event.defaultPrevented) return
      emit('select-node', node, { additive: event.shiftKey || event.metaKey || event.ctrlKey })
    })

  nodes.append('rect')
    .attr('x', -NODE_W / 2)
    .attr('y', -NODE_H / 2)
    .attr('width', NODE_W)
    .attr('height', NODE_H)
    .attr('rx', 8)
    .attr('fill', '#ffffff')
    .attr('stroke', d => {
      if (d.id === props.selectedNodeId) return '#0f172a'
      if (d.id === props.searchNodeId) return '#7c3aed'
      if (isInPath(d.id)) return '#ef4444'
      return '#dbe3ed'
    })
    .attr('stroke-width', d => (d.id === props.selectedNodeId || d.id === props.searchNodeId || isInPath(d.id)) ? 2.4 : 1.2)
    .attr('filter', d => d.id === props.selectedNodeId || isInPath(d.id) ? 'url(#node-glow)' : null)

  nodes.append('circle')
    .attr('cx', -NODE_W / 2 + 21)
    .attr('cy', 0)
    .attr('r', d => 8 + Math.min(d.difficulty || 1, 5))
    .attr('fill', d => getColor(d))
    .attr('opacity', d => {
      if (props.heatmapMode) return 0.96
      const mastery = props.masteryMap[d.id]
      return mastery?.level === 'unlearned' ? 0.58 : 1
    })

  nodes.append('text')
    .attr('class', 'graph-node-title')
    .attr('x', -NODE_W / 2 + 42)
    .attr('y', -6)
    .text(d => shortText(d.name, 13))

  nodes.append('text')
    .attr('class', 'graph-node-meta')
    .attr('x', -NODE_W / 2 + 42)
    .attr('y', 15)
    .text(d => {
      const mastery = props.masteryMap[d.id]
      const suffix = mastery ? ` · ${mastery.score}分` : ''
      return `${displayCategory(d.category)}${suffix}`
    })

  nodes.append('title')
    .text(d => `${d.name || d.id}\n${displayCategory(d.category)}\n难度 ${d.difficulty || 1}`)

  if (props.editMode || layoutMode.value === 'force') {
    nodes.call(createDragBehavior(links, nodes, edgeLabels, width, height))
  }

  if (layoutMode.value === 'force') {
    simulation = createForceSimulation(nodeData, linkData, width, height)
    simulation.on('tick', () => {
      if (!props.editMode) clampNodes(nodeData, width, height)
      render(links, nodes, edgeLabels)
    })

    for (let i = 0; i < 130; i++) simulation.tick()
    if (!props.editMode) clampNodes(nodeData, width, height)
    render(links, nodes, edgeLabels)
    simulation.alpha(0.18).restart()
    setTimeout(() => fitToScreen(), 260)
  } else {
    render(links, nodes, edgeLabels)
    setTimeout(() => fitToScreen(), 80)
  }
}

function seedForceLayout(nodes, links, width, height) {
  const depths = nodeDepths(nodes, links)
  const lanes = categoryLanes(nodes)
  const maxDepth = Math.max(1, ...depths.values())
  const maxLane = Math.max(1, lanes.size - 1)

  nodes.forEach((node, index) => {
    const depth = depths.get(node.id) || 0
    const lane = lanes.get(node.category || '未分类') || 0
    node.x = VIEW_PADDING + (width - VIEW_PADDING * 2) * (depth / maxDepth) + ((index % 3) - 1) * 18
    node.y = VIEW_PADDING + (height - VIEW_PADDING * 2) * (lane / maxLane) + ((index % 5) - 2) * 16
  })
}

function createForceSimulation(nodes, links, width, height) {
  const depths = nodeDepths(nodes, links)
  const lanes = categoryLanes(nodes)
  const maxDepth = Math.max(1, ...depths.values())
  const maxLane = Math.max(1, lanes.size - 1)

  return d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(d => d.type === 'RELATED_TO' ? 142 : 176).strength(0.56))
    .force('charge', d3.forceManyBody().strength(-620).theta(0.85))
    .force('collide', d3.forceCollide(NODE_W * 0.58).strength(0.92).iterations(3))
    .force('x', d3.forceX(d => VIEW_PADDING + (width - VIEW_PADDING * 2) * ((depths.get(d.id) || 0) / maxDepth)).strength(0.16))
    .force('y', d3.forceY(d => VIEW_PADDING + (height - VIEW_PADDING * 2) * ((lanes.get(d.category || '未分类') || 0) / maxLane)).strength(0.12))
    .force('center', d3.forceCenter(width / 2, height / 2).strength(0.04))
    .alpha(0.85)
    .alphaMin(0.04)
    .alphaDecay(0.035)
}

function createDragBehavior(links, nodes, edgeLabels, width, height) {
  return d3.drag()
    .container(() => g?.node() || svgEl.value)
    .on('start', (event, node) => {
      if (!event.active && simulation) simulation.alphaTarget(0.25).restart()
      node.fx = node.x
      node.fy = node.y
    })
    .on('drag', (event, node) => {
      node.x = event.x
      node.y = event.y
      node.fx = event.x
      node.fy = event.y
      if (!props.editMode) clampNodes([node], width, height)
      render(links, nodes, edgeLabels)
    })
    .on('end', (event, node) => {
      if (!event.active && simulation) simulation.alphaTarget(0)
      if (props.editMode) {
        node.fx = node.x
        node.fy = node.y
        emit('node-position-change', { id: node.id, x: node.x, y: node.y })
      } else {
        node.fx = null
        node.fy = null
      }
    })
}

function clampNodes(nodes, width, height) {
  nodes.forEach(node => {
    node.x = Math.max(VIEW_PADDING, Math.min(width - VIEW_PADDING, node.x || width / 2))
    node.y = Math.max(VIEW_PADDING, Math.min(height - VIEW_PADDING, node.y || height / 2))
  })
}

function createArrow(defs, id, color) {
  defs.append('marker')
    .attr('id', id)
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 11)
    .attr('refY', 0)
    .attr('markerWidth', 7)
    .attr('markerHeight', 7)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', color)
}

function createGlow(defs) {
  const filter = defs.append('filter')
    .attr('id', 'node-glow')
    .attr('x', '-30%')
    .attr('y', '-40%')
    .attr('width', '160%')
    .attr('height', '180%')
  filter.append('feDropShadow')
    .attr('dx', 0)
    .attr('dy', 8)
    .attr('stdDeviation', 5)
    .attr('flood-color', '#0f172a')
    .attr('flood-opacity', 0.16)
}

function render(links, nodes, edgeLabels) {
  links.attr('d', linkPath)
  nodes.attr('transform', d => `translate(${d.x},${d.y})`)
  edgeLabels
    .attr('x', d => (coord(d.source).x + coord(d.target).x) / 2)
    .attr('y', d => (coord(d.source).y + coord(d.target).y) / 2 - 8)
}

function updateVisualState() {
  if (!g) return
  const pathSet = pathEdgeSet()

  g.selectAll('.graph-link')
    .attr('class', d => `graph-link ${isPathLink(d, pathSet) ? 'is-path' : ''} ${isSelectedLink(d) ? 'is-selected' : ''}`)
    .attr('stroke', d => {
      if (isSelectedLink(d)) return '#0f172a'
      return isPathLink(d, pathSet) ? '#ef4444' : (d.type === 'RELATED_TO' ? '#94a3b8' : '#64748b')
    })
    .attr('stroke-width', d => isSelectedLink(d) ? 4 : (isPathLink(d, pathSet) ? 3 : Math.max(1.4, (d.weight || 1) * 1.2)))
    .attr('stroke-opacity', d => isPathLink(d, pathSet) ? 0.95 : 0.42)
    .attr('marker-end', d => {
      if (isPathLink(d, pathSet)) return 'url(#arrow-path)'
      return d.type === 'RELATED_TO' ? 'url(#arrow-related)' : 'url(#arrow-prerequisite)'
    })

  const edgeLabels = g.select('.graph-edge-label-layer')
    .selectAll('text')
    .data(
      currentLinks.filter(link => isPathLink(link, pathSet) || layoutMode.value === 'dagre'),
      d => `${normalizeId(d.source)}-${normalizeId(d.target)}-${d.type || ''}`,
    )

  edgeLabels.join(
    enter => enter.append('text')
      .attr('class', 'graph-edge-label')
      .text(d => relationLabel(d.type))
      .attr('fill', d => isPathLink(d, pathSet) ? '#dc2626' : '#64748b')
      .attr('x', d => (coord(d.source).x + coord(d.target).x) / 2)
      .attr('y', d => (coord(d.source).y + coord(d.target).y) / 2 - 8),
    update => update
      .text(d => relationLabel(d.type))
      .attr('fill', d => isPathLink(d, pathSet) ? '#dc2626' : '#64748b')
      .attr('x', d => (coord(d.source).x + coord(d.target).x) / 2)
      .attr('y', d => (coord(d.source).y + coord(d.target).y) / 2 - 8),
    exit => exit.remove(),
  )

  const nodeCards = g.selectAll('.graph-node-card')
    .attr('class', d => `graph-node-card state-${getNodeState(d)}`)

  nodeCards.select('rect')
    .attr('stroke', d => {
      if (d.id === props.selectedNodeId) return '#0f172a'
      if (d.id === props.searchNodeId) return '#7c3aed'
      if (isInPath(d.id)) return '#ef4444'
      return '#dbe3ed'
    })
    .attr('stroke-width', d => (d.id === props.selectedNodeId || d.id === props.searchNodeId || isInPath(d.id)) ? 2.4 : 1.2)
    .attr('filter', d => d.id === props.selectedNodeId || isInPath(d.id) ? 'url(#node-glow)' : null)

  nodeCards.select('circle')
    .attr('fill', d => getColor(d))
    .attr('opacity', d => {
      if (props.heatmapMode) return 0.96
      const mastery = props.masteryMap[d.id]
      return mastery?.level === 'unlearned' ? 0.58 : 1
    })

  nodeCards.select('.graph-node-meta')
    .text(d => {
      const mastery = props.masteryMap[d.id]
      const suffix = mastery ? ` · ${mastery.score}分` : ''
      return `${displayCategory(d.category)}${suffix}`
    })
}

function linkPath(link) {
  const source = coord(link.source)
  const target = coord(link.target)
  const dx = target.x - source.x
  const dy = target.y - source.y
  const distance = Math.max(1, Math.sqrt(dx * dx + dy * dy))
  const sx = source.x + (dx / distance) * (NODE_W / 2 - 4)
  const sy = source.y + (dy / distance) * (NODE_H / 2 - 4)
  const tx = target.x - (dx / distance) * (NODE_W / 2 + 8)
  const ty = target.y - (dy / distance) * (NODE_H / 2 + 8)

  if (layoutMode.value === 'dagre') {
    const mx = sx + (tx - sx) * 0.5
    return `M${sx},${sy} C${mx},${sy} ${mx},${ty} ${tx},${ty}`
  }

  const curve = Math.min(90, Math.max(28, distance * 0.18))
  const cx = (sx + tx) / 2 - (dy / distance) * curve
  const cy = (sy + ty) / 2 + (dx / distance) * curve
  return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
}

function coord(value) {
  if (typeof value === 'object') return value
  return currentNodes.find(node => node.id === value) || { x: 0, y: 0 }
}

function fitToScreen() {
  if (!svg || !g || !zoomBehavior || !container.value) return
  const graphNode = g.node()
  if (!graphNode) return

  let box
  try {
    box = graphNode.getBBox()
  } catch {
    return
  }
  if (!box || !Number.isFinite(box.width) || !Number.isFinite(box.height) || box.width === 0 || box.height === 0) return

  const rect = container.value.getBoundingClientRect()
  const scale = Math.max(
    MIN_ZOOM,
    Math.min(MAX_ZOOM, Math.min(
      (rect.width - VIEW_PADDING) / box.width,
      (rect.height - VIEW_PADDING) / box.height,
    )),
  )
  const x = rect.width / 2 - (box.x + box.width / 2) * scale
  const y = rect.height / 2 - (box.y + box.height / 2) * scale

  svg.transition().duration(520).ease(d3.easeCubicOut).call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(x, y).scale(scale),
  )
}

function locateNode(nodeId) {
  if (!svg || !zoomBehavior || !container.value) return
  const target = currentNodes.find(node => node.id === nodeId)
  if (!target) return
  const rect = container.value.getBoundingClientRect()
  const scale = 1.25
  svg.transition().duration(520).ease(d3.easeCubicOut).call(
    zoomBehavior.transform,
    d3.zoomIdentity
      .translate(rect.width / 2 - target.x * scale, rect.height / 2 - target.y * scale)
      .scale(scale),
  )
}

function zoomBy(scale) {
  if (!svg || !zoomBehavior) return
  svg.transition().duration(220).ease(d3.easeCubicOut).call(zoomBehavior.scaleBy, scale)
}

function exportSVG() {
  if (!svgEl.value) return
  const clone = svgEl.value.cloneNode(true)
  const rect = container.value?.getBoundingClientRect()
  clone.setAttribute('width', String(Math.round(rect?.width || 1200)))
  clone.setAttribute('height', String(Math.round(rect?.height || 800)))
  const svgText = new XMLSerializer().serializeToString(clone)
  download('knowledge-graph.svg', 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgText))
}

function exportJSON() {
  const data = { nodes: props.nodes, links: props.links, mastery: props.masteryMap }
  download('knowledge-graph.json', 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(data, null, 2)))
}

function exportCSV() {
  const rows = ['id,name,category,difficulty,estimated_time,mastery_score']
  props.nodes.forEach(node => {
    const mastery = props.masteryMap[node.id]
    rows.push([
      node.id,
      '"' + String(node.name || '').replaceAll('"', '""') + '"',
      node.category || '',
      node.difficulty || 1,
      node.estimated_time || 0,
      mastery?.score || 0,
    ].join(','))
  })
  download('knowledge-graph.csv', 'data:text/csv;charset=utf-8,' + encodeURIComponent(rows.join('\n')))
}

function download(filename, url) {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
}

function scheduleInit() {
  nextTick(() => initGraph())
}

watch(
  () => [props.nodes, props.links, props.editMode],
  scheduleInit,
  { deep: true },
)

watch(
  () => [props.highlightedPath, props.masteryMap, props.heatmapData, props.heatmapMode, props.selectedNodeId, props.searchNodeId, props.selectedLinkKey, props.selectedNodeIds, props.relationSourceId],
  () => nextTick(() => updateVisualState()),
  { deep: true },
)

onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    if (props.nodes.length) scheduleInit()
  })
  if (container.value) resizeObserver.observe(container.value)
  if (props.nodes.length) scheduleInit()
})

onBeforeUnmount(() => {
  if (simulation) simulation.stop()
  if (resizeObserver) resizeObserver.disconnect()
})

defineExpose({ fitToScreen, locateNode, zoomBy })
</script>
