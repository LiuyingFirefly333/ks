import { ref } from 'vue'

import { authApi } from '../api/index.js'
import { clearAuthSession, getSavedRole, saveUserProfile } from '../services/authStorage.js'

export function useAuthSession() {
  const user = ref(null)

  function setUser(nextUser) {
    user.value = nextUser
  }

  async function restoreSession() {
    const savedRole = getSavedRole()
    if (!savedRole) return
    try {
      const data = await authApi.me()
      if (data.user) {
        user.value = { ...data.user, role: data.role }
        saveUserProfile(user.value)
      }
    } catch {
      clearAuthSession()
      user.value = null
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {}
    clearAuthSession()
    user.value = null
  }

  function updateProfile(updatedUser) {
    user.value = { ...(user.value || {}), ...updatedUser }
    saveUserProfile(user.value)
  }

  return {
    user,
    setUser,
    restoreSession,
    logout,
    updateProfile,
  }
}
