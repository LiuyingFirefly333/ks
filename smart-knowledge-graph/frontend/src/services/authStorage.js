const USER_KEY = 'user'
const ROLE_KEY = 'role'

export function getAuthToken() {
  return ''
}

export function getSavedRole() {
  return localStorage.getItem(ROLE_KEY) || 'student'
}

export function saveAuthSession(user, role) {
  localStorage.setItem(USER_KEY, JSON.stringify({ ...user, role }))
  localStorage.setItem(ROLE_KEY, role)
}

export function saveUserProfile(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  if (user?.role) localStorage.setItem(ROLE_KEY, user.role)
}

export function clearAuthSession() {
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(ROLE_KEY)
}
