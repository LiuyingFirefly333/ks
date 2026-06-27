<template>
  <div class="login-wrapper">
    <section class="login-hero">
      <div class="login-brand">
        <span class="brand-mark large">KG</span>
        <span>智能知识图谱学习系统</span>
      </div>
      <h1>把知识点、学情和 AI 答疑放在一张图里。</h1>
      <p>面向学生自学、教师教研和知识库运维的一体化学习工作台。</p>
      <div class="login-highlights">
        <span>知识图谱</span>
        <span>AI 问答</span>
        <span>路径推荐</span>
        <span>错题溯源</span>
      </div>
    </section>

    <section class="login-card">
      <div class="login-header">
        <h2>{{ mode === 'login' ? '欢迎回来' : '创建账号' }}</h2>
        <p>{{ mode === 'login' ? '登录后进入个人学习工作台' : '注册后即可开始构建学习档案' }}</p>
      </div>

      <form @submit.prevent="handleSubmit" class="login-form">
        <div class="form-row">
          <label>人员类型</label>
          <select v-model="role">
            <option value="student">学生</option>
            <option value="teacher">教师</option>
            <option value="admin">管理员</option>
          </select>
        </div>
        <div class="form-row" v-if="mode === 'register'">
          <label>姓名</label>
          <input v-model="form.name" placeholder="输入姓名" />
        </div>
        <div class="form-row">
          <label>邮箱</label>
          <div class="input-icon-field">
            <input v-model="form.email" type="email" placeholder="name@example.com" />
            <span class="input-trailing-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <rect x="3" y="5" width="18" height="14" rx="2" />
                <path d="m3 7 9 6 9-6" />
              </svg>
            </span>
          </div>
        </div>
        <div class="form-row">
          <label>密码</label>
          <div class="password-field">
            <input
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="输入密码"
            />
            <button
              type="button"
              class="password-toggle"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              :title="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              <svg v-if="showPassword" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 3l18 18" />
                <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                <path d="M9.9 4.2A10.6 10.6 0 0 1 12 4c6.5 0 10 8 10 8a18 18 0 0 1-3.2 4.5" />
                <path d="M6.5 6.5C3.7 8.3 2 12 2 12s3.5 8 10 8a10.8 10.8 0 0 0 5.5-1.5" />
              </svg>
              <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          </div>
        </div>
        <div class="form-row" v-if="mode === 'register'">
          <label>确认密码</label>
          <div class="password-field">
            <input
              v-model="form.confirmPassword"
              :type="showConfirmPassword ? 'text' : 'password'"
              placeholder="再次输入密码"
            />
            <button
              type="button"
              class="password-toggle"
              :aria-label="showConfirmPassword ? '隐藏确认密码' : '显示确认密码'"
              :title="showConfirmPassword ? '隐藏确认密码' : '显示确认密码'"
              @click="showConfirmPassword = !showConfirmPassword"
            >
              <svg v-if="showConfirmPassword" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 3l18 18" />
                <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                <path d="M9.9 4.2A10.6 10.6 0 0 1 12 4c6.5 0 10 8 10 8a18 18 0 0 1-3.2 4.5" />
                <path d="M6.5 6.5C3.7 8.3 2 12 2 12s3.5 8 10 8a10.8 10.8 0 0 0 5.5-1.5" />
              </svg>
              <svg v-else viewBox="0 0 24 24" aria-hidden="true">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          </div>
        </div>
        <div v-if="error" class="error-msg">{{ error }}</div>
        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? '处理中...' : (mode === 'login' ? '登录' : '创建账号') }}
        </button>
        <button
          v-if="mode === 'login'"
          type="button"
          class="btn-secondary-full"
          :disabled="loading"
          @click="mode = 'register'; clearError()"
        >
          注册
        </button>
        <button
          v-else
          type="button"
          class="btn-secondary-full"
          :disabled="loading"
          @click="mode = 'login'; clearError()"
        >
          返回登录
        </button>
      </form>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { authApi } from '../api/index.js'
import { saveAuthSession } from '../services/authStorage.js'

const emit = defineEmits(['login-success'])
const mode = ref('login')
const loading = ref(false)
const error = ref('')
const form = reactive({ name: '', email: '', password: '', confirmPassword: '' })
const role = ref('student')
const showPassword = ref(false)
const showConfirmPassword = ref(false)

function clearError() {
  error.value = ''
}

async function handleSubmit() {
  if (!form.email || !form.password) {
    error.value = '邮箱和密码不能为空'
    return
  }
  if (mode.value === 'register' && !form.name) {
    error.value = '姓名不能为空'
    return
  }
  if (mode.value === 'register' && !form.confirmPassword) {
    error.value = '确认密码不能为空'
    return
  }
  if (mode.value === 'register' && form.password !== form.confirmPassword) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  error.value = ''
  try {
    let result
    if (mode.value === 'login' && role.value === 'student') {
      result = await authApi.login(form.email, form.password)
    } else if (mode.value === 'login' && role.value === 'teacher') {
      result = await authApi.loginTeacher(form.email, form.password)
    } else if (mode.value === 'login' && role.value === 'admin') {
      result = await authApi.loginAdmin(form.email, form.password)
    } else if (mode.value === 'register' && role.value === 'student') {
      result = await authApi.register(form.name, form.email, form.password)
    } else if (mode.value === 'register' && role.value === 'admin') {
      result = await authApi.registerAdmin(form.name, form.email, form.password)
    } else {
      result = await authApi.registerTeacher(form.name, form.email, form.password)
    }
    const user = result.student || result.teacher || result.admin
    if (user) {
      saveAuthSession(user, role.value)
      emit('login-success', { ...user, role: role.value })
    } else {
      error.value = '登录返回数据异常，请检查后端服务'
    }
  } catch (e) {
    error.value = e.normalizedMessage || e.response?.data?.error || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>
