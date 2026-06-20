<template>
  <LoginView v-if="!student" @login-success="onLoginSuccess" />
  <DashboardView v-else :student="student" @logout="onLogout" />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import LoginView from './views/LoginView.vue'
import DashboardView from './views/DashboardView.vue'
import { authApi } from './api/index.js'

const student = ref(null)

function onLoginSuccess(s) {
  student.value = s
}

function onLogout() {
  localStorage.removeItem('token')
  localStorage.removeItem('student')
  student.value = null
}

onMounted(async () => {
  const token = localStorage.getItem('token')
  if (token) {
    try {
      const data = await authApi.me()
      if (data.student) {
        student.value = data.student
      }
    } catch {
      localStorage.removeItem('token')
      localStorage.removeItem('student')
    }
  }
})
</script>
