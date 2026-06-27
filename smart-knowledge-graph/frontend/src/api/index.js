import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = 'Bearer ' + token
  }
  return config
})

api.interceptors.response.use(
  response => response,
  error => {
    const payload = error.response?.data
    if (payload?.error && typeof payload.error === 'object') {
      error.normalizedMessage = payload.error.message
    } else if (typeof payload?.error === 'string') {
      error.normalizedMessage = payload.error
    }
    return Promise.reject(error)
  }
)

// Auth
export const authApi = {
  register: (name, email, password) =>
    api.post('/auth/register', { name, email, password }).then(r => r.data),
  login: (email, password) =>
    api.post('/auth/login', { email, password }).then(r => r.data),
  me: () => api.get('/auth/me').then(r => r.data),
  registerTeacher: (name, email, password) =>
    api.post('/auth/teacher/register', { name, email, password }).then(r => r.data),
  loginTeacher: (email, password) =>
    api.post('/auth/teacher/login', { email, password }).then(r => r.data),
  registerAdmin: (name, email, password) =>
    api.post('/auth/admin/register', { name, email, password }).then(r => r.data),
  loginAdmin: (email, password) =>
    api.post('/auth/admin/login', { email, password }).then(r => r.data),
}

// Courses
export const courseApi = {
  list: () => api.get('/courses').then(r => r.data),
  get: (id) => api.get('/courses/' + id).then(r => r.data),
  create: (data, teacherId) => api.post('/courses', { ...data, teacher_id: teacherId }).then(r => r.data),
}

// Knowledge
export const knowledgeApi = {
  list: (category, courseId) => api.get('/knowledge', { params: { category, course_id: courseId } }).then(r => r.data),
  search: (q, courseId) => api.get('/knowledge/search', { params: { q, course_id: courseId } }).then(r => r.data),
  get: (id) => api.get('/knowledge/' + id).then(r => r.data),
  create: (data) => api.post('/knowledge', data).then(r => r.data),
  update: (id, data) => api.put('/knowledge/' + id, data).then(r => r.data),
  delete: (id) => api.delete('/knowledge/' + id).then(r => r.data),
}

// Resources
export const resourceApi = {
  list: (params = {}) => api.get('/resources', { params }).then(r => r.data),
  listByKnowledge: (nodeId, params = {}) =>
    api.get('/resources/knowledge/' + nodeId, { params }).then(r => r.data),
  get: (id) => api.get('/resources/' + id).then(r => r.data),
  create: (data) => api.post('/resources', data).then(r => r.data),
  update: (id, data) => api.put('/resources/' + id, data).then(r => r.data),
  delete: (id) => api.delete('/resources/' + id).then(r => r.data),
  attach: (id, data) => api.post('/resources/' + id + '/attach', data).then(r => r.data),
  detach: (id, nodeId) => api.post('/resources/' + id + '/detach', { node_id: nodeId }).then(r => r.data),
  batchAttach: (resourceIds, nodeIds, options = {}) =>
    api.post('/resources/batch-attach', { resource_ids: resourceIds, node_ids: nodeIds, ...options }).then(r => r.data),
  batchStatus: (resourceIds, status) =>
    api.patch('/resources/batch-status', { resource_ids: resourceIds, status }).then(r => r.data),
  migrateLegacy: (courseId) =>
    api.post('/resources/migrate-legacy', { course_id: courseId }).then(r => r.data),
}

// Graph
export const graphApi = {
  getGraph: (category, courseId, studentId) =>
    api.get('/graph', { params: { category, course_id: courseId, student_id: studentId } }).then(r => r.data),
  getCategories: (courseId) => api.get('/graph/categories', { params: { course_id: courseId } }).then(r => r.data),
  createRelation: (source, target, type, weight) =>
    api.post('/graph/relations', { source, target, type, weight }).then(r => r.data),
  updateRelation: (source, target, type, newSource, newTarget, newType, weight) =>
    api.put('/graph/relations', {
      source,
      target,
      type,
      new_source: newSource,
      new_target: newTarget,
      new_type: newType,
      weight,
    }).then(r => r.data),
  deleteRelation: (source, target, type) =>
    api.delete('/graph/relations', { data: { source, target, type } }).then(r => r.data),
  getNeighbors: (nodeId) => api.get('/graph/neighbors', { params: { nodeId } }).then(r => r.data),
}

// Recommend
export const recommendApi = {
  recommendPath: (mastered, target) =>
    api.post('/recommend/path', { mastered, target }).then(r => r.data),
  recommendPathForStudent: (studentId, target) =>
    api.post('/recommend/path', { student_id: studentId, target }).then(r => r.data),
  recommendEasyPath: (studentId, target) =>
    api.post('/recommend/path/easy', { student_id: studentId, target }).then(r => r.data),
  recommendThoroughPath: (studentId, target) =>
    api.post('/recommend/path/thorough', { student_id: studentId, target }).then(r => r.data),
  getPrerequisites: (nodeId) =>
    api.get('/recommend/prerequisites/' + nodeId).then(r => r.data),
  getRoadmap: (targetId, studentId) =>
    api.get('/recommend/roadmap/' + targetId, { params: { student_id: studentId } }).then(r => r.data),
  setMastery: (studentId, nodeId, score) =>
    api.post('/recommend/mastery', { student_id: studentId, node_id: nodeId, score }).then(r => r.data),
  getMastery: (studentId) =>
    api.get('/recommend/mastery/' + studentId).then(r => r.data),
  deleteMastery: (studentId, nodeId) =>
    api.delete('/recommend/mastery', { data: { student_id: studentId, node_id: nodeId } }).then(r => r.data),
}

// AI Q&A
export const qaApi = {
  createSession: (title, courseId, nodeId) =>
    api.post('/qa/sessions', { title, course_id: courseId, node_id: nodeId }).then(r => r.data),
  listSessions: (q) =>
    api.get('/qa/sessions', { params: { q } }).then(r => r.data),
  getSession: (sessionId) =>
    api.get('/qa/sessions/' + sessionId).then(r => r.data),
  deleteSession: (sessionId) =>
    api.delete('/qa/sessions/' + sessionId).then(r => r.data),
  searchHistory: (q) =>
    api.get('/qa/history/search', { params: { q } }).then(r => r.data),
  ask: (question, courseId, nodeId, sessionId) =>
    api.post('/qa/ask', { question, course_id: courseId, node_id: nodeId, session_id: sessionId }).then(r => r.data),
  askStream: (question, courseId, nodeId, sessionId, onToken, onSources, onDone, onError) => {
    const token = localStorage.getItem('token')
    return fetch('/api/qa/ask/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {}),
      },
      body: JSON.stringify({ question, course_id: courseId, node_id: nodeId, session_id: sessionId }),
    }).then(async response => {
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6))
              if (event.type === 'token') onToken(event.data)
              else if (event.type === 'sources') onSources(event.data, event.session_id)
              else if (event.type === 'done') onDone(event.message_id)
              else if (event.type === 'error') onError(event.data)
            } catch {}
          }
        }
      }
    }).catch(onError)
  },
  submitFeedback: (payload) => api.post('/qa/feedback', payload).then(r => r.data),
  listFeedback: (status) => api.get('/qa/feedback', { params: { status } }).then(r => r.data),
  analytics: (days) => api.get('/qa/analytics', { params: { days } }).then(r => r.data),
  reviewFeedback: (id, status, note) =>
    api.post('/qa/feedback/' + id + '/review', { status, note }).then(r => r.data),
}

// Analytics
export const analyticsApi = {
  calcMastery: (studentId, courseId) =>
    api.post('/analytics/mastery/calc', { student_id: studentId, course_id: courseId }).then(r => r.data),
  classHeatmap: (classId, courseId) =>
    api.post('/analytics/class/heatmap', { class_id: classId, course_id: courseId }).then(r => r.data),
  classReport: (classId, courseId) =>
    api.get('/analytics/class/' + classId + '/report', { params: { course_id: courseId } }).then(r => r.data),
  exportClassReport: (classId, courseId) =>
    api.get('/analytics/class/' + classId + '/report/export', { params: { course_id: courseId }, responseType: 'blob' }).then(r => r.data),
}

// Teaching research
export const teachingApi = {
  questionStats: (courseId) =>
    api.get('/teaching/question-stats', { params: { course_id: courseId } }).then(r => r.data),
  exportMindmap: (courseId) =>
    api.get('/teaching/mindmap/export', { params: { course_id: courseId }, responseType: 'blob' }).then(r => r.data),
  uploadResource: (formData) =>
    api.post('/teaching/resources/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data),
  extractKnowledge: (payload) =>
    api.post('/teaching/extract', payload).then(r => r.data),
  importOutline: (formData) =>
    api.post('/teaching/outline/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data),
}

// Profile
export const profileApi = {
  get: () => api.get('/profile').then(r => r.data),
  update: (payload) => api.put('/profile', payload).then(r => r.data),
  stats: (courseId) => api.get('/profile/stats', { params: { course_id: courseId } }).then(r => r.data),
  growth: (courseId, semester) =>
    api.get('/profile/growth', { params: { course_id: courseId, semester } }).then(r => r.data),
  createSnapshot: (courseId, semester) =>
    api.post('/profile/growth/snapshot', { course_id: courseId, semester }).then(r => r.data),
  exportGrowth: (courseId, semester) =>
    api.get('/profile/growth/export', { params: { course_id: courseId, semester }, responseType: 'blob' }).then(r => r.data),
}

// Classroom
export const classroomApi = {
  listClasses: (teacherId) => api.get('/classroom/classes', { params: { teacher_id: teacherId } }).then(r => r.data),
  createClass: (name, grade, subject, teacherId) => api.post('/classroom/classes', { name, grade, subject, teacher_id: teacherId }).then(r => r.data),
  getStudents: (classId) => api.get('/classroom/classes/' + classId + '/students').then(r => r.data),
  addStudent: (classId, studentId) => api.post('/classroom/classes/' + classId + '/students', { student_id: studentId }).then(r => r.data),
  removeStudent: (classId, studentId) => api.delete('/classroom/classes/' + classId + '/students/' + studentId).then(r => r.data),
}

// Exam
export const examApi = {
  addError: (studentId, nodeId, question, correctAnswer, studentAnswer, errorReason) =>
    api.post('/exam/errors', { student_id: studentId, node_id: nodeId, question, correct_answer: correctAnswer, student_answer: studentAnswer, error_reason: errorReason }).then(r => r.data),
  listErrors: (studentId) => api.get('/exam/errors/' + studentId).then(r => r.data),
  deleteError: (errorId) => api.delete('/exam/errors/' + errorId).then(r => r.data),
  errorTrace: (errorId) => api.get('/exam/errors/' + errorId + '/trace').then(r => r.data),
  listQuestions: (params = {}) => api.get('/exam/questions', { params }).then(r => r.data),
  createQuestion: (data) => api.post('/exam/questions', data).then(r => r.data),
  selectQuestions: (data) => api.post('/exam/questions/select', data).then(r => r.data),
  generateTest: (studentId, courseId, count) =>
    api.post('/exam/test/generate', { student_id: studentId, course_id: courseId, count: count || 10 }).then(r => r.data),
  submitTest: (paperId, answers) =>
    api.post('/exam/test/' + paperId + '/submit', { answers }).then(r => r.data),
  listSubjectiveReviews: (params = {}) =>
    api.get('/exam/subjective/reviews', { params }).then(r => r.data),
  gradeSubjective: (attemptId, score, feedback) =>
    api.post('/exam/subjective/' + attemptId + '/grade', { score, feedback }).then(r => r.data),
}

// Admin
export const adminApi = {
  registerAdmin: (name, email, password) => api.post('/auth/admin/register', { name, email, password }).then(r => r.data),
  loginAdmin: (email, password) => api.post('/auth/admin/login', { email, password }).then(r => r.data),
  listUsers: () => api.get('/admin/users').then(r => r.data),
  createUser: (payload) => api.post('/admin/users', payload).then(r => r.data),
  assignUserRole: (type, id, role) => api.patch('/admin/users/' + type + '/' + id + '/role', { role }).then(r => r.data),
  importUsers: (users) => api.post('/admin/users/import', { users }).then(r => r.data),
  exportUsers: () => api.get('/admin/users/export', { responseType: 'blob' }).then(r => r.data),
  disableUser: (type, id) => api.post('/admin/users/' + type + '/' + id + '/disable').then(r => r.data),
  validateGraph: () => api.get('/admin/graph/validate').then(r => r.data),
  fixGraphIssue: (issue) => api.post('/admin/graph/fix', { issue }).then(r => r.data),
  listGraphBackups: () => api.get('/admin/graph/backups').then(r => r.data),
  createGraphBackup: (label) => api.post('/admin/graph/backup', { label }).then(r => r.data),
  cleanGraphData: () => api.post('/admin/graph/clean').then(r => r.data),
  cleanupRedundantNodes: () => api.post('/admin/graph/cleanup-redundant').then(r => r.data),
  incrementalUpdate: (payload) => api.post('/admin/graph/incremental-update', payload).then(r => r.data),
  dashboard: (params = {}) => {
    const query = typeof params === 'string' ? { course_id: params } : params
    return api.get('/admin/dashboard', { params: query }).then(r => r.data)
  },
}

// Discuss
export const discussApi = {
  listComments: (nodeId) => api.get('/discuss/comments/' + nodeId).then(r => r.data),
  addComment: (userId, nodeId, content, role) => api.post('/discuss/comments', { user_id: userId, node_id: nodeId, content, role }).then(r => r.data),
  deleteComment: (commentId) => api.delete('/discuss/comments/' + commentId).then(r => r.data),
}

export default api
