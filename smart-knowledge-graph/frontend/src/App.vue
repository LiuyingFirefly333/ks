<template>
  <LoginView v-if="!user" @login-success="onLoginSuccess" />
  <DashboardView v-else :user="user" @logout="onLogout" />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import LoginView from './views/LoginView.vue'
import DashboardView from './views/DashboardView.vue'
import { authApi } from './api/index.js'

const user = ref(null)

function onLoginSuccess(u) {
  user.value = u
}

function onLogout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  localStorage.removeItem('role')
  user.value = null
}

onMounted(async () => {
  const token = localStorage.getItem('token')
  const savedRole = localStorage.getItem('role') || 'student'
  if (token && savedRole) {
    try {
      const data = await authApi.me(savedRole)
      if (data.user) {
        user.value = { ...data.user, role: data.role }
        localStorage.setItem('role', data.role)
      }
    } catch {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem('role')
    }
  }
})
</script>
