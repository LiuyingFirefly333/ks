<template>
  <div class="toast-stack" aria-live="polite">
    <button
      v-for="toast in toasts"
      :key="toast.id"
      class="toast-item"
      :class="toast.type"
      @click="dismissToast(toast.id)"
    >
      {{ toast.message }}
    </button>
  </div>
</template>

<script setup>
import { useToast } from '../composables/useToast.js'

const { toasts, dismissToast } = useToast()
</script>
