<template>
  <div ref="container" class="graph-wrapper">
    <svg ref="svgEl" class="graph-svg"></svg>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount, nextTick } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  links: { type: Array, default: () => [] },
  highlightedPath: { type: Array, default: () => [] },
  searchNodeId: { type: String, default: null },
  selectedNodeId: { type: String, default: null },
})

const emit = defineEmits(['select-node'])

const container = ref(null)
const svgEl = ref(null)

let simulation = null
let svg = null
let g = null
let linkGroup = null
let nodeGroup = null
let labelGroup = null
let transform = d3.zoomIdentity
let zoomBehavior = null

const CATEGORY_COLORS = {
  '高等数学-基础': '#6366f1',
  '高等数学-极限': '#22c55e',
  '高等数学-导数': '#f59e0b',
  '高等数学-积分': '#3b82f6',
  '高等数学-微分方程': '#ef4444',
}

function getColor(cat) {
  return CATEGORY_COLORS[cat] || '#8b5cf6'
}

function isInPath(nodeId) {
  return props.highlightedPath.includes(nodeId)
}

function initGraph() {
  if (!container.value) return
  const rect = container.value.getBoundingClientRect()
  const width = rect.width
  const height = rect.height

  svg = d3.select(svgEl.value)
  svg.selectAll('*').remove()

  // 用 defs 存箭头
  const defs = svg.append('defs')
  defs.append('marker')
    .attr('id', 'arrow-prerequisite')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 22)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#64748b')

  defs.append('marker')
    .attr('id', 'arrow-path')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 22)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#ef4444')

  g = svg.append('g')

  // 缩放
  zoomBehavior = d3.zoom()
    .scaleExtent([0.15, 5])
    .on('zoom', (event) => {
      transform = event.transform
      g.attr('transform', event.transform)
    })

  svg.call(zoomBehavior)

  // ---- 力导向 ----
  const nodeData = props.nodes.map(n => ({ ...n }))
  const linkData = props.links.map(l => ({ ...l }))

  simulation = d3.forceSimulation(nodeData)
    .force('link', d3.forceLink(linkData).id(d => d.id).distance(140))
    .force('charge', d3.forceManyBody().strength(-350))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide(50))
    .alphaDecay(0.03)

  // 连线
  linkGroup = g.append('g').attr('class', 'links')
  const link = linkGroup.selectAll('line')
    .data(linkData)
    .join('line')
    .attr('stroke', d => isInPath(d.source.id) && isInPath(d.target.id) ? '#ef4444' : '#475569')
    .attr('stroke-width', d => (isInPath(d.source.id) && isInPath(d.target.id) ? 3 : Math.max(1, (d.weight || 1) * 1.5)))
    .attr('stroke-opacity', 0.5)
    .attr('marker-end', d => (isInPath(d.source.id) && isInPath(d.target.id)) ? 'url(#arrow-path)' : 'url(#arrow-prerequisite)')
    .attr('stroke-dasharray', d => d.type === 'RELATED_TO' ? '5,3' : 'none')

  // 节点组
  nodeGroup = g.append('g').attr('class', 'nodes')
  const node = nodeGroup.selectAll('g')
    .data(nodeData)
    .join('g')
    .attr('cursor', 'pointer')
    .call(d3.drag()
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

  // 圆
  node.append('circle')
    .attr('r', d => 8 + (d.difficulty || 1) * 3)
    .attr('fill', d => getColor(d.category))
    .attr('stroke', d => {
      if (d.id === props.selectedNodeId) return '#fff'
      if (isInPath(d.id)) return '#ef4444'
      return 'transparent'
    })
    .attr('stroke-width', d => {
      if (d.id === props.selectedNodeId || isInPath(d.id)) return 3
      return 0
    })
    .style('filter', d => d.id === props.searchNodeId ? 'url(#glow)' : 'none')

  // 搜索高亮的发光滤镜
  const glowFilter = defs.append('filter').attr('id', 'glow')
  glowFilter.append('feGaussianBlur').attr('stdDeviation', 4).attr('result', 'blur')
  const merge = glowFilter.append('feMerge')
  merge.append('feMergeNode').attr('in', 'blur')
  merge.append('feMergeNode').attr('in', 'SourceGraphic')

  // 标签
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

  // 搜索节点加脉冲环
  let pulseCircle = g.selectAll('.pulse-ring').data(
    props.searchNodeId ? nodeData.filter(n => n.id === props.searchNodeId) : []
  )
  pulseCircle.exit().remove()
  pulseCircle = pulseCircle.enter().append('circle')
    .attr('class', 'pulse-ring')
    .attr('r', 10)
    .attr('fill', 'none')
    .attr('stroke', '#f59e0b')
    .attr('stroke-width', 3)
    .style('animation', 'pulse-ring 1.5s ease-out infinite')
  if (props.searchNodeId && nodeData.length > 0) {
    const found = nodeData.find(n => n.id === props.searchNodeId)
    if (found) {
      pulseCircle.attr('cx', found.x).attr('cy', found.y)
    }
  }

  // 点击
  node.on('click', (event, d) => {
    emit('select-node', d)
  })

  // 悬浮高亮邻接
  node.on('mouseenter', (event, d) => {
    const neighborIds = new Set()
    linkData.forEach(l => {
      const sid = typeof l.source === 'object' ? l.source.id : l.source
      const tid = typeof l.target === 'object' ? l.target.id : l.target
      if (sid === d.id) neighborIds.add(tid)
      if (tid === d.id) neighborIds.add(sid)
    })
    neighborIds.add(d.id)

    link.attr('stroke-opacity', l => {
      const sid = typeof l.source === 'object' ? l.source.id : l.source
      const tid = typeof l.target === 'object' ? l.target.id : l.target
      return (neighborIds.has(sid) && neighborIds.has(tid)) ? 0.7 : 0.08
    })
    node.selectAll('circle').attr('opacity', n => neighborIds.has(n.id) ? 1 : 0.25)
    label.attr('opacity', n => neighborIds.has(n.id) ? 1 : 0.15)
  })

  node.on('mouseleave', () => {
    link.attr('stroke-opacity', 0.5)
    node.selectAll('circle').attr('opacity', 1)
    label.attr('opacity', 1)
  })

  // simulation tick
  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
    node.attr('transform', d => `translate(${d.x},${d.y})`)
    label.attr('x', d => d.x).attr('y', d => d.y)
    pulseCircle.attr('cx', d => d.x).attr('cy', d => d.y)
  })

  // 初始居中
  setTimeout(() => {
    fitToScreen()
  }, 500)
}

function fitToScreen() {
  if (!svg || !g) return
  const rect = container.value?.getBoundingClientRect()
  if (!rect) return
  const cx = rect.width / 2
  const cy = rect.height / 2
  svg.transition().duration(500).call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(cx, cy).scale(0.8)
  )
}

function locateNode(nodeId) {
  if (!simulation || !svg) return
  const data = simulation.nodes()
  const target = data.find(n => n.id === nodeId)
  if (!target) return
  const rect = container.value?.getBoundingClientRect()
  if (!rect) return
  const cx = rect.width / 2
  const cy = rect.height / 2
  svg.transition().duration(600).call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(cx - target.x * 1.2, cy - target.y * 1.2).scale(1.2)
  )
}

// 重新计算路径高亮
function updatePathHighlight() {
  if (!linkGroup || !nodeGroup) return
  linkGroup.selectAll('line')
    .attr('stroke', d => {
      const sid = typeof d.source === 'object' ? d.source.id : d.source
      const tid = typeof d.target === 'object' ? d.target.id : d.target
      return isInPath(sid) && isInPath(tid) ? '#ef4444' : '#475569'
    })
    .attr('stroke-width', d => {
      const sid = typeof d.source === 'object' ? d.source.id : d.source
      const tid = typeof d.target === 'object' ? d.target.id : d.target
      return (isInPath(sid) && isInPath(tid)) ? 3 : Math.max(1, (d.weight || 1) * 1.5)
    })
    .attr('marker-end', d => {
      const sid = typeof d.source === 'object' ? d.source.id : d.source
      const tid = typeof d.target === 'object' ? d.target.id : d.target
      return (isInPath(sid) && isInPath(tid)) ? 'url(#arrow-path)' : 'url(#arrow-prerequisite)'
    })

  nodeGroup.selectAll('circle')
    .attr('stroke', d => {
      if (d.id === props.selectedNodeId) return '#fff'
      if (isInPath(d.id)) return '#ef4444'
      return 'transparent'
    })
    .attr('stroke-width', d => {
      if (d.id === props.selectedNodeId || isInPath(d.id)) return 3
      return 0
    })

  labelGroup.selectAll('text')
    .attr('font-size', d => isInPath(d.id) ? 14 : 12)
    .attr('fill', d => isInPath(d.id) ? '#fca5a5' : '#cbd5e1')
    .attr('font-weight', d => isInPath(d.id) ? 'bold' : 'normal')
}

watch(() => props.highlightedPath, () => {
  nextTick(() => updatePathHighlight())
}, { deep: true })

watch(() => props.selectedNodeId, () => {
  nextTick(() => updatePathHighlight())
})

watch(() => props.searchNodeId, (val) => {
  if (val) {
    nextTick(() => locateNode(val))
  }
})

watch(() => props.nodes, (newNodes) => {
  if (newNodes.length > 0) {
    nextTick(() => initGraph())
  }
})

onMounted(() => {
  if (props.nodes.length > 0) {
    nextTick(() => initGraph())
  }
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
</style>
