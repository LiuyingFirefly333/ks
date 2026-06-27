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

      <div class="segmented login-tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'; clearError()">登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'; clearError()">注册</button>
      </div>

      <div class="segmented role-tabs">
        <button :class="{ active: role === 'student' }" @click="role = 'student'">学生</button>
        <button :class="{ active: role === 'teacher' }" @click="role = 'teacher'">教师</button>
        <button :class="{ active: role === 'admin' }" @click="role = 'admin'">管理员</button>
      </div>

      <form @submit.prevent="handleSubmit" class="login-form">
        <div class="form-row" v-if="mode === 'register'">
          <label>姓名</label>
          <input v-model="form.name" placeholder="输入姓名" />
        </div>
        <div class="form-row">
          <label>邮箱</label>
          <input v-model="form.email" type="email" placeholder="name@example.com" />
        </div>
        <div class="form-row">
          <label>密码</label>
          <input v-model="form.password" type="password" placeholder="输入密码" />
        </div>
        <div v-if="error" class="error-msg">{{ error }}</div>
        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? '处理中...' : (mode === 'login' ? '登录' : '注册') }}
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
const form = reactive({ name: '', email: '', password: '' })
const role = ref('student')

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
