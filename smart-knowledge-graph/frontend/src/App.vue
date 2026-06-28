<template>
  <LoginView v-if="!user" @login-success="setUser" />
  <DashboardView v-else :user="user" @logout="logout" @profile-updated="updateProfile" />
  <AppToast />
</template>

<script setup>
import { onMounted } from 'vue'

import { useAuthSession } from './composables/useAuthSession.js'
import AppToast from './components/AppToast.vue'
import LoginView from './views/LoginView.vue'
import DashboardView from './views/DashboardView.vue'

const { user, setUser, restoreSession, logout, updateProfile } = useAuthSession()

onMounted(restoreSession)
</script>
