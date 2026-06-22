<template>
  <div v-if="node" class="node-detail-panel">
    <div class="node-detail-header">
      <h3>{{ node.name }}</h3>
      <button class="close" @click="$emit('close')">&times;</button>
    </div>

    <div class="node-detail-body">
      <div class="field">
        <div class="label">分类</div>
        <div class="value">{{ node.category }}</div>
      </div>

      <div class="field">
        <div class="label">难度</div>
        <div class="diff-dots">
          <span
            v-for="i in 5"
            :key="i"
            class="dot"
            :class="i <= (node.difficulty || 1) ? 'fill' : 'empty'"
          ></span>
        </div>
      </div>

      <div class="field" v-if="node.estimated_time">
        <div class="label">预计学习时长</div>
        <div class="value est-time">{{ node.estimated_time }} 分钟</div>
      </div>

      <div class="field">
        <div class="label">描述</div>
        <div class="value">{{ node.description || '暂无描述' }}</div>
      </div>

      <div class="field" v-if="node.video_urls && node.video_urls.length">
        <div class="label">视频资源 ({{ node.video_urls.length }})</div>
        <div v-for="(url, idx) in node.video_urls" :key="'v' + idx" class="resource-item">
          <div v-if="isBilibili(url)" class="video-embed">
            <iframe :src="bilibiliEmbed(url)" frameborder="0" scrolling="no" allowfullscreen></iframe>
          </div>
          <div v-else-if="isYoutube(url)" class="video-embed">
            <iframe
              :src="youtubeEmbed(url)"
              frameborder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
            ></iframe>
          </div>
          <a v-else :href="url" target="_blank" class="resource-link">视频链接 {{ idx + 1 }}</a>
        </div>
      </div>

      <div class="field" v-if="node.exercises && node.exercises.length">
        <div class="label">习题资源 ({{ node.exercises.length }})</div>
        <div v-for="(url, idx) in node.exercises" :key="'e' + idx" class="resource-item">
          <a :href="url" target="_blank" class="resource-link exercise-link">习题 {{ idx + 1 }}</a>
        </div>
      </div>

      <div class="field" v-if="neighbors.length">
        <div class="label">关联知识点 ({{ neighbors.length }})</div>
        <div
          v-for="nb in neighbors"
          :key="nb.node.id"
          class="node-item"
          @click="$emit('locate', nb.node)"
        >
          <span>{{ nb.node.name }}</span>
          <span class="cat-tag">{{ nb.relation.type || '关联' }}</span>
        </div>
      </div>

      <div class="field" style="margin-top:8px">
        <DiscussPanel :nodeId="node.id" :userId="userId" :userRole="userRole" />
      </div>

      <div class="form-actions" style="margin-top:12px">
        <button class="ghost" style="flex:1" @click="$emit('show-roadmap', node.id)">查看学习路线</button>
        <button style="flex:1" @click="$emit('ask-ai', node)">问 AI</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { graphApi } from '../api/index.js'
import DiscussPanel from './DiscussPanel.vue'

const props = defineProps({
  node: { type: Object, default: null },
  userId: { type: String, default: '' },
  userRole: { type: String, default: 'student' },
})

defineEmits(['close', 'locate', 'show-roadmap', 'ask-ai'])

const neighbors = ref([])

watch(() => props.node, async (val) => {
  if (val && val.id) {
    try {
      neighbors.value = await graphApi.getNeighbors(val.id)
    } catch {
      neighbors.value = []
    }
  } else {
    neighbors.value = []
  }
}, { immediate: true })

function isBilibili(url) {
  return /bilibili\.com\/video\//.test(url)
}

function isYoutube(url) {
  return /(youtube\.com\/watch|youtu\.be\/)/.test(url)
}

function bilibiliEmbed(url) {
  const bvid = url.match(/BV[a-zA-Z0-9]+/)?.[0] || ''
  const page = url.match(/[?&]p=(\d+)/)?.[1] || 1
  return 'https://player.bilibili.com/player.html?bvid=' + bvid + '&page=' + page
}

function youtubeEmbed(url) {
  const vid = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/)?.[1] || ''
  return 'https://www.youtube.com/embed/' + vid
}
</script>
