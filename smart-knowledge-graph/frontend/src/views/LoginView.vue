<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="login-header">
        <h1>知识图谱</h1>
        <p>智能课程知识图谱系统</p>
      </div>

      <div class="login-tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'; clearError()">登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'; clearError()">注册</button>
      </div>

      <form @submit.prevent="handleSubmit" class="login-form">
        <div class="row" v-if="mode === 'register'">
          <label>姓名</label>
          <input v-model="form.name" placeholder="输入姓名" />
        </div>
        <div class="row">
          <label>邮箱</label>
          <input v-model="form.email" type="email" placeholder="输入邮箱" />
        </div>
        <div class="row">
          <label>密码</label>
          <input v-model="form.password" type="password" placeholder="输入密码" />
        </div>
        <div v-if="error" class="error-msg">{{ error }}</div>
        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? '处理中...' : (mode === 'login' ? '登录' : '注册') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { authApi } from '../api/index.js'

const emit = defineEmits(['login-success'])
const mode = ref('login')
const loading = ref(false)
const error = ref('')
const form = reactive({ name: '', email: '', password: '' })

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
    if (mode.value === 'login') {
      result = await authApi.login(form.email, form.password)
    } else {
      result = await authApi.register(form.name, form.email, form.password)
    }
    if (result.student && result.student.token) {
      localStorage.setItem('token', result.student.token)
      localStorage.setItem('student', JSON.stringify(result.student))
      emit('login-success', result.student)
    }
  } catch (e) {
    error.value = e.response?.data?.error || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--bg-primary);
}
.login-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 36px 32px;
  width: 380px;
}
.login-header {
  text-align: center;
  margin-bottom: 24px;
}
.login-header h1 {
  font-size: 22px;
  margin: 0 0 4px;
}
.login-header p {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
}
.login-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 20px;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.login-tabs button {
  flex: 1;
  padding: 8px 0;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  cursor: pointer;
}
.login-tabs button.active {
  background: var(--accent-blue);
  color: #fff;
}
.login-form .row {
  margin-bottom: 14px;
}
.login-form label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}
.login-form input {
  width: 100%;
  padding: 8px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 14px;
  box-sizing: border-box;
}
.login-form input:focus {
  outline: none;
  border-color: var(--accent-blue);
}
.btn-primary {
  width: 100%;
  padding: 10px;
  background: var(--accent-blue);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  margin-top: 4px;
}
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error-msg {
  color: var(--accent-red);
  font-size: 13px;
  margin-bottom: 10px;
}
</style>
