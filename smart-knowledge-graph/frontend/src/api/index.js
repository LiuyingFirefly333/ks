import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：自动附加 token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ===== 认证 =====
export const authApi = {
  register: (name, email, password) =>
    api.post('/auth/register', { name, email, password }).then(r => r.data),
  login: (email, password) =>
    api.post('/auth/login', { email, password }).then(r => r.data),
  me: () => api.get('/auth/me').then(r => r.data),
}

// ===== 课程 =====
export const courseApi = {
  list: () => api.get('/courses').then(r => r.data),
  get: (id) => api.get(`/courses/${id}`).then(r => r.data),
  create: (data) => api.post('/courses', data).then(r => r.data),
}

// 知识点
export const knowledgeApi = {
  list: (category, courseId) => api.get('/knowledge', { params: { category, course_id: courseId } }).then(r => r.data),
  search: (q, courseId) => api.get('/knowledge/search', { params: { q, course_id: courseId } }).then(r => r.data),
  get: (id) => api.get(`/knowledge/${id}`).then(r => r.data),
  create: (data) => api.post('/knowledge', data).then(r => r.data),
  update: (id, data) => api.put(`/knowledge/${id}`, data).then(r => r.data),
  delete: (id) => api.delete(`/knowledge/${id}`).then(r => r.data),
}

// 图谱
export const graphApi = {
  getGraph: (category, courseId, studentId) =>
    api.get('/graph', { params: { category, course_id: courseId, student_id: studentId } }).then(r => r.data),
  getCategories: (courseId) => api.get('/graph/categories', { params: { course_id: courseId } }).then(r => r.data),
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
  recommendPathForStudent: (studentId, target) =>
    api.post('/recommend/path', { student_id: studentId, target }).then(r => r.data),
  getPrerequisites: (nodeId) =>
    api.get(`/recommend/prerequisites/${nodeId}`).then(r => r.data),
  getRoadmap: (targetId) =>
    api.get(`/recommend/roadmap/${targetId}`).then(r => r.data),
  setMastery: (studentId, nodeId, score) =>
    api.post('/recommend/mastery', { student_id: studentId, node_id: nodeId, score }).then(r => r.data),
  getMastery: (studentId) =>
    api.get(`/recommend/mastery/${studentId}`).then(r => r.data),
  deleteMastery: (studentId, nodeId) =>
    api.delete('/recommend/mastery', { data: { student_id: studentId, node_id: nodeId } }).then(r => r.data),
}

export default api
