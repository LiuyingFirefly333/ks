export const NODE_W = 172
export const NODE_H = 58
export const MIN_ZOOM = 0.18
export const MAX_ZOOM = 3.5
export const VIEW_PADDING = 76

export const CATEGORY_COLORS = {
  '高等数学-基础': '#2563eb',
  '高等数学-极限': '#16a34a',
  '高等数学-导数': '#f59e0b',
  '高等数学-积分': '#0891b2',
  '高等数学-微分方程': '#dc2626',
}

export const MASTERY_COLORS = {
  proficient: '#16a34a',
  fair: '#f59e0b',
  weak: '#f97316',
  unlearned: '#94a3b8',
}

export const HEAT_COLORS = ['#16a34a', '#84cc16', '#f59e0b', '#f97316', '#ef4444', '#b91c1c']

export const DEFAULT_PATH_STYLES = {
  shortest: { label: '最短路径', color: '#ef4444' },
  easy: { label: '最轻松', color: '#16a34a' },
  thorough: { label: '最扎实', color: '#2563eb' },
  roadmap: { label: '路线图', color: '#7c3aed' },
}

export function getHeatColor(avgScore) {
  if (avgScore >= 85) return HEAT_COLORS[0]
  if (avgScore >= 70) return HEAT_COLORS[1]
  if (avgScore >= 55) return HEAT_COLORS[2]
  if (avgScore >= 40) return HEAT_COLORS[3]
  if (avgScore > 0) return HEAT_COLORS[4]
  return '#94a3b8'
}

export function hashColor(key) {
  const palette = ['#2563eb', '#0f766e', '#7c3aed', '#db2777', '#0891b2', '#ea580c', '#475569']
  const value = String(key || '未分类')
  let hash = 0
  for (let i = 0; i < value.length; i++) hash = (hash + value.charCodeAt(i) * (i + 1)) % palette.length
  return palette[hash]
}
