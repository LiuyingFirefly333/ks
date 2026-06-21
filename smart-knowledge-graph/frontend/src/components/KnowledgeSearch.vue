<template>
  <div class="search-box">
    <input
      v-model="query"
      placeholder="搜索知识点..."
      @input="onSearch"
      @focus="showResults = true"
    />
    <div v-if="showResults && results.length" class="search-results">
      <div
        v-for="r in results"
        :key="r.id"
        class="item"
        @click="select(r)"
      >
        <span>{{ r.name }}</span>
        <span class="cat">{{ r.category }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { knowledgeApi } from '../api/index.js'

const emit = defineEmits(['locate'])
const props = defineProps({
  courseId: { type: String, default: null },
})

const query = ref('')
const results = ref([])
const showResults = ref(false)
let debounceTimer = null

function onSearch() {
  clearTimeout(debounceTimer)
  if (!query.value.trim()) {
    results.value = []
    return
  }
  debounceTimer = setTimeout(async () => {
    try {
      results.value = await knowledgeApi.search(query.value.trim(), props.courseId)
    } catch {
      results.value = []
    }
  }, 250)
}

function select(node) {
  query.value = node.name
  showResults.value = false
  emit('locate', node)
}
</script>
