import { DEFAULT_PATH_STYLES } from './graphConfig.js'

export function normalizeId(value) {
  return typeof value === 'object' ? value.id : value
}

export function normalizeHighlightedPath(group, index = 0) {
  if (Array.isArray(group)) {
    return {
      type: index === 0 ? 'shortest' : `path-${index + 1}`,
      label: index === 0 ? '推荐路径' : `路径 ${index + 1}`,
      color: ['#ef4444', '#16a34a', '#2563eb'][index] || '#7c3aed',
      nodes: group.map(normalizeId).filter(Boolean),
    }
  }

  const type = group?.type || `path-${index + 1}`
  const defaults = DEFAULT_PATH_STYLES[type] || {}
  const rawNodes = group?.nodes || group?.path || []
  return {
    type,
    label: group?.label || defaults.label || `路径 ${index + 1}`,
    color: group?.color || defaults.color || '#7c3aed',
    nodes: rawNodes.map(normalizeId).filter(Boolean),
    total_estimated_time: group?.total_estimated_time || 0,
  }
}

export function highlightedPathGroups(highlightedPaths = [], highlightedPath = []) {
  if (highlightedPaths.length) {
    return highlightedPaths.map(normalizeHighlightedPath).filter(group => group.nodes.length)
  }
  if (highlightedPath.length) return [normalizeHighlightedPath(highlightedPath, 0)]
  return []
}

export function nodePathMatches(nodeId, groups) {
  return groups.filter(group => group.nodes.includes(nodeId))
}

export function pathEdgeSet(groups) {
  const map = new Map()
  groups.forEach(group => {
    for (let i = 0; i < group.nodes.length - 1; i++) {
      const key = `${group.nodes[i]}->${group.nodes[i + 1]}`
      const matches = map.get(key) || []
      matches.push(group)
      map.set(key, matches)
    }
  })
  return map
}

export function pathNodeMap(groups) {
  const map = new Map()
  groups.forEach(group => {
    group.nodes.forEach(nodeId => {
      const matches = map.get(nodeId) || []
      matches.push(group)
      map.set(nodeId, matches)
    })
  })
  return map
}

export function pathMatchesForLink(link, pathSet) {
  const source = normalizeId(link.source)
  const target = normalizeId(link.target)
  return pathSet.get(`${source}->${target}`) || []
}

export function pathMatchForLink(link, pathSet) {
  return pathMatchesForLink(link, pathSet)[0] || null
}

export function pathLabelForLink(link, pathSet) {
  const matches = pathMatchesForLink(link, pathSet)
  if (!matches.length) return ''
  return matches.map(item => item.label).join(' / ')
}

export function pathNodeColors(nodeId, nodeMap) {
  const seen = new Set()
  return (nodeMap.get(nodeId) || [])
    .filter(group => {
      if (seen.has(group.type)) return false
      seen.add(group.type)
      return true
    })
    .map(group => group.color)
}
