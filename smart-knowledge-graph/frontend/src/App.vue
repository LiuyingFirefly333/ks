<template>
  <LoginView v-if="!user" @login-success="onLoginSuccess" />
  <DashboardView v-else :user="user" @logout="onLogout" @profile-updated="onProfileUpdated" />
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

async function onLogout() {
  try {
    await authApi.logout()
  } catch {}
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  localStorage.removeItem('role')
  user.value = null
}

function onProfileUpdated(updatedUser) {
  user.value = { ...(user.value || {}), ...updatedUser }
  localStorage.setItem('user', JSON.stringify(user.value))
  if (updatedUser.role) localStorage.setItem('role', updatedUser.role)
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
