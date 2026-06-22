<template>
  <div ref="container" class="graph-wrapper">
    <div class="graph-toolbar-top">
      <button :class="{ active: layoutMode === 'force' }" @click="setLayout('force')" title="力导向布局">F</button>
      <button :class="{ active: layoutMode === 'dagre' }" @click="setLayout('dagre')" title="分层布局">L</button>
      <span class="toolbar-sep"></span>
      <button @click="exportSVG" title="导出 SVG 图片">SVG</button>
      <button @click="exportJSON" title="导出 JSON 数据">JSON</button>
      <button @click="exportCSV" title="导出 CSV 表格">CSV</button>
    </div>
    <svg ref="svgEl" class="graph-svg"></svg>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount, nextTick } from 'vue'
import * as d3 from 'd3'

let dagre = null

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  links: { type: Array, default: () => [] },
  highlightedPath: { type: Array, default: () => [] },
  searchNodeId: { type: String, default: null },
  selectedNodeId: { type: String, default: null },
  masteryMap: { type: Object, default: () => ({}) },
  heatmapData: { type: Array, default: () => [] },
  heatmapMode: { type: Boolean, default: false },
})

const emit = defineEmits(['select-node'])

const container = ref(null)
const svgEl = ref(null)
const layoutMode = ref('force')

let simulation = null
let svg = null
let g = null
let linkGroup = null
let nodeGroup = null
let labelGroup = null
let zoomBehavior = null

const CATEGORY_COLORS = {
  '高等数学-基础': '#6366f1',
  '高等数学-极限': '#22c55e',
  '高等数学-导数': '#f59e0b',
  '高等数学-积分': '#3b82f6',
  '高等数学-微分方程': '#ef4444',
}

const MASTERY_COLORS = {
  proficient: '#22c55e',
  fair: '#eab308',
  weak: '#f97316',
  unlearned: '#6b7280',
}

const HEAT_COLORS = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444', '#dc2626']

function getHeatColor(avgScore) {
  if (avgScore >= 85) return HEAT_COLORS[0]
  if (avgScore >= 70) return HEAT_COLORS[1]
  if (avgScore >= 55) return HEAT_COLORS[2]
  if (avgScore >= 40) return HEAT_COLORS[3]
  if (avgScore > 0) return HEAT_COLORS[4]
  return '#6b7280'
}

function getColor(node) {
  if (props.heatmapMode) {
    const heat = props.heatmapData.find(x => x.node_id === node.id)
    if (heat) return getHeatColor(heat.avg_score)
  }

  const mastery = props.masteryMap[node.id]
  if (mastery) return MASTERY_COLORS[mastery.level] || CATEGORY_COLORS[node.category] || '#8b5cf6'

  return CATEGORY_COLORS[node.category] || '#8b5cf6'
}

function isInPath(nodeId) {
  return props.highlightedPath.includes(nodeId)
}

async function layoutWithDagre(nodes, links) {
  if (!dagre) {
    try {
      dagre = (await import('dagre')).default
    } catch {
      return
    }
  }

  const graph = new dagre.graphlib.Graph()
  graph.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 120, marginx: 40, marginy: 40 })
  graph.setDefaultEdgeLabel(() => ({}))

  nodes.forEach(node => graph.setNode(node.id, { width: 120, height: 30 }))
  links.forEach(link => {
    const source = typeof link.source === 'object' ? link.source.id : link.source
    const target = typeof link.target === 'object' ? link.target.id : link.target
    graph.setEdge(source, target)
  })

  dagre.layout(graph)

  const rect = container.value?.getBoundingClientRect()
  const width = rect?.width || 800
  const height = rect?.height || 600
  const graphWidth = graph.graph().width || 800
  const graphHeight = graph.graph().height || 600

  nodes.forEach(node => {
    const dagreNode = graph.node(node.id)
    if (dagreNode) {
      node.x = dagreNode.x + width / 2 - graphWidth / 2
      node.y = dagreNode.y + height / 2 - graphHeight / 2
    }
  })
}

function setLayout(mode) {
  layoutMode.value = mode
  if (svg) initGraph()
}

function exportSVG() {
  if (!svgEl.value) return
  const svgText = new XMLSerializer().serializeToString(svgEl.value.cloneNode(true))
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

async function initGraph() {
  if (!container.value) return

  const rect = container.value.getBoundingClientRect()
  const width = rect.width
  const height = rect.height

  if (simulation) simulation.stop()

  svg = d3.select(svgEl.value)
  svg.selectAll('*').remove()

  const defs = svg.append('defs')
  createArrow(defs, 'arrow-prerequisite', '#64748b')
  createArrow(defs, 'arrow-path', '#ef4444')

  g = svg.append('g')
  zoomBehavior = d3.zoom()
    .scaleExtent([0.15, 5])
    .on('zoom', event => {
      g.attr('transform', event.transform)
    })
  svg.call(zoomBehavior)

  const nodeData = props.nodes.map(node => ({ ...node }))
  const linkData = props.links.map(link => ({ ...link }))

  if (layoutMode.value === 'dagre') await layoutWithDagre(nodeData, linkData)

  if (layoutMode.value === 'force') {
    simulation = d3.forceSimulation(nodeData)
      .force('link', d3.forceLink(linkData).id(d => d.id).distance(140))
      .force('charge', d3.forceManyBody().strength(-350))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(50))
      .alphaDecay(0.03)
  } else {
    simulation = null
  }

  linkGroup = g.append('g').attr('class', 'links')
  const link = linkGroup.selectAll('line')
    .data(linkData)
    .join('line')
    .attr('stroke', d => isPathLink(d) ? '#ef4444' : '#475569')
    .attr('stroke-width', d => isPathLink(d) ? 3 : Math.max(1, (d.weight || 1) * 1.5))
    .attr('stroke-opacity', 0.5)
    .attr('stroke-dasharray', d => d.type === 'RELATED_TO' ? '5,3' : 'none')
    .attr('marker-end', d => isPathLink(d) ? 'url(#arrow-path)' : 'url(#arrow-prerequisite)')

  nodeGroup = g.append('g').attr('class', 'nodes')
  const node = nodeGroup.selectAll('g')
    .data(nodeData)
    .join('g')
    .attr('cursor', 'pointer')

  if (layoutMode.value === 'force') {
    node.call(
      d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
    )
  }

  node.append('circle')
    .attr('r', d => 8 + (d.difficulty || 1) * 3)
    .attr('fill', d => getColor(d))
    .attr('stroke', d => {
      if (d.id === props.selectedNodeId) return '#fff'
      if (isInPath(d.id)) return '#ef4444'
      return 'transparent'
    })
    .attr('stroke-width', d => (d.id === props.selectedNodeId || isInPath(d.id)) ? 3 : 0)
    .attr('opacity', d => {
      if (props.heatmapMode) return 0.9
      const mastery = props.masteryMap[d.id]
      return mastery?.level === 'unlearned' ? 0.4 : 1
    })

  labelGroup = g.append('g').attr('class', 'labels')
  const label = labelGroup.selectAll('text')
    .data(nodeData)
    .join('text')
    .text(d => d.name)
    .attr('dx', d => 14 + (d.difficulty || 1) * 3)
    .attr('dy', 4)
    .attr('font-size', d => isInPath(d.id) ? 14 : 12)
    .attr('fill', d => isInPath(d.id) ? '#fca5a5' : '#cbd5e1')
    .attr('font-weight', d => isInPath(d.id) ? 'bold' : 'normal')
    .style('pointer-events', 'none')
    .style('text-shadow', '0 1px 3px rgba(0,0,0,0.8)')

  node.on('click', (event, d) => emit('select-node', d))

  if (layoutMode.value === 'dagre') {
    renderStaticLayout(link, node, label)
    setTimeout(() => fitToScreen(), 100)
    return
  }

  simulation.on('tick', () => renderStaticLayout(link, node, label))
  setTimeout(() => fitToScreen(), 500)
}

function createArrow(defs, id, color) {
  defs.append('marker')
    .attr('id', id)
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 22)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', color)
}

function renderStaticLayout(link, node, label) {
  link
    .attr('x1', d => d.source.x)
    .attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x)
    .attr('y2', d => d.target.y)
  node.attr('transform', d => `translate(${d.x},${d.y})`)
  label.attr('x', d => d.x).attr('y', d => d.y)
}

function isPathLink(link) {
  const source = typeof link.source === 'object' ? link.source.id : link.source
  const target = typeof link.target === 'object' ? link.target.id : link.target
  return isInPath(source) && isInPath(target)
}

function fitToScreen() {
  if (!svg || !g || !zoomBehavior) return
  const rect = container.value?.getBoundingClientRect()
  if (!rect) return
  svg.transition().duration(500).call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(rect.width / 2, rect.height / 2).scale(0.8)
  )
}

function locateNode(nodeId) {
  if (!svg || !zoomBehavior) return
  const data = simulation?.nodes() || props.nodes
  const target = data.find(node => node.id === nodeId)
  if (!target) return
  const rect = container.value?.getBoundingClientRect()
  if (!rect) return
  svg.transition().duration(600).call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(rect.width / 2 - target.x * 1.2, rect.height / 2 - target.y * 1.2).scale(1.2)
  )
}

watch(() => [props.highlightedPath, props.masteryMap, props.heatmapData], () => {
  nextTick(() => {
    if (linkGroup) initGraph()
  })
}, { deep: true })

watch(() => props.nodes, (newNodes) => {
  if (newNodes.length > 0) nextTick(() => initGraph())
})

onMounted(() => {
  if (props.nodes.length > 0) nextTick(() => initGraph())
})

onBeforeUnmount(() => {
  if (simulation) simulation.stop()
})

defineExpose({ fitToScreen, locateNode })
</script>

<style scoped>
.graph-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
}

.graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.graph-toolbar-top {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 20;
  display: flex;
  gap: 4px;
  align-items: center;
}

.graph-toolbar-top button {
  min-width: 30px;
  height: 30px;
  padding: 0 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 11px;
  cursor: pointer;
}

.graph-toolbar-top button:hover,
.graph-toolbar-top button.active {
  background: var(--primary);
  color: #fff;
}

.toolbar-sep {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 4px;
}
</style>
