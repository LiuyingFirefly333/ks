import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// 知识点
export const knowledgeApi = {
  list: (category) => api.get('/knowledge', { params: { category } }).then(r => r.data),
  search: (q) => api.get('/knowledge/search', { params: { q } }).then(r => r.data),
  get: (id) => api.get(`/knowledge/${id}`).then(r => r.data),
  create: (data) => api.post('/knowledge', data).then(r => r.data),
  update: (id, data) => api.put(`/knowledge/${id}`, data).then(r => r.data),
  delete: (id) => api.delete(`/knowledge/${id}`).then(r => r.data),
}

// 图谱
export const graphApi = {
  getGraph: (category) => api.get('/graph', { params: { category } }).then(r => r.data),
  getCategories: () => api.get('/graph/categories').then(r => r.data),
  createRelation: (source, target, type, weight) =>
    api.post('/graph/relations', { source, target, type, weight }).then(r => r.data),
  deleteRelation: (source, target, type) =>
    api.delete('/graph/relations', { data: { source, target, type } }).then(r => r.data),
  getNeighbors: (nodeId) => api.get('/graph/neighbors', { params: { nodeId } }).then(r => r.data),
}

// 推荐
export const recommendApi = {
  recommendPath: (mastered, target) =>
    api.post('/recommend/path', { mastered, target }).then(r => r.data),
  getPrerequisites: (nodeId) =>
    api.get(`/recommend/prerequisites/${nodeId}`).then(r => r.data),
  getRoadmap: (targetId) =>
    api.get(`/recommend/roadmap/${targetId}`).then(r => r.data),
}

export default api
