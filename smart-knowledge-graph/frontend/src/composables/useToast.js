import { ref } from 'vue'

const toasts = ref([])

export function useToast() {
  function showToast(message, type = 'info', timeout = 3200) {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    toasts.value = [...toasts.value, { id, message, type }]
    window.setTimeout(() => dismissToast(id), timeout)
  }

  function dismissToast(id) {
    toasts.value = toasts.value.filter(item => item.id !== id)
  }

  return {
    toasts,
    showToast,
    dismissToast,
  }
}
