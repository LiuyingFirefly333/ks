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

// Auth
export const authApi = {
  register: (name, email, password) =>
    api.post('/auth/register', { name, email, password }).then(r => r.data),
  login: (email, password) =>
    api.post('/auth/login', { email, password }).then(r => r.data),
  me: (role = 'student') => api.get('/auth/me', { params: { role } }).then(r => r.data),
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

// Graph
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
  getRoadmap: (targetId) =>
    api.get('/recommend/roadmap/' + targetId).then(r => r.data),
  setMastery: (studentId, nodeId, score) =>
    api.post('/recommend/mastery', { student_id: studentId, node_id: nodeId, score }).then(r => r.data),
  getMastery: (studentId) =>
    api.get('/recommend/mastery/' + studentId).then(r => r.data),
  deleteMastery: (studentId, nodeId) =>
    api.delete('/recommend/mastery', { data: { student_id: studentId, node_id: nodeId } }).then(r => r.data),
}

// AI Q&A
export const qaApi = {
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
              else if (event.type === 'done') onDone()
              else if (event.type === 'error') onError(event.data)
            } catch {}
          }
        }
      }
    }).catch(onError)
  },
}

// Analytics
export const analyticsApi = {
  calcMastery: (studentId, courseId) =>
    api.post('/analytics/mastery/calc', { student_id: studentId, course_id: courseId }).then(r => r.data),
  classHeatmap: (classId, courseId) =>
    api.post('/analytics/class/heatmap', { class_id: classId, course_id: courseId }).then(r => r.data),
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
  generateTest: (studentId, courseId, count) =>
    api.post('/exam/test/generate', { student_id: studentId, course_id: courseId, count: count || 10 }).then(r => r.data),
}

// Admin
export const adminApi = {
  registerAdmin: (name, email, password) => api.post('/auth/admin/register', { name, email, password }).then(r => r.data),
  loginAdmin: (email, password) => api.post('/auth/admin/login', { email, password }).then(r => r.data),
  listUsers: () => api.get('/admin/users').then(r => r.data),
  disableUser: (type, id) => api.post('/admin/users/' + type + '/' + id + '/disable').then(r => r.data),
  validateGraph: () => api.get('/admin/graph/validate').then(r => r.data),
  dashboard: (courseId) => api.get('/admin/dashboard', { params: { course_id: courseId } }).then(r => r.data),
}

// Discuss
export const discussApi = {
  listComments: (nodeId) => api.get('/discuss/comments/' + nodeId).then(r => r.data),
  addComment: (userId, nodeId, content, role) => api.post('/discuss/comments', { user_id: userId, node_id: nodeId, content, role }).then(r => r.data),
  deleteComment: (commentId) => api.delete('/discuss/comments/' + commentId).then(r => r.data),
}

export default api