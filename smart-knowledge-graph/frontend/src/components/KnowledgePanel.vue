<template>
  <div v-if="node" class="node-detail-panel">
    <div class="node-detail-header">
      <div>
        <div class="panel-eyebrow">知识点详情</div>
        <h3>{{ node.name }}</h3>
      </div>
      <button class="icon-button" @click="$emit('close')" title="关闭">×</button>
    </div>

    <div class="node-detail-body">
      <div class="detail-card">
        <div class="field">
          <div class="label">分类</div>
          <div class="value">{{ node.category || '未分类' }}</div>
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
          <div class="value muted-text">{{ node.description || '暂无描述' }}</div>
        </div>
      </div>

      <div class="field" v-if="resources.length">
        <div class="section-title">学习资源 <span>{{ resources.length }}</span></div>
        <div v-for="resource in resources" :key="resource.id" class="resource-item">
          <div v-if="resource.type === 'video' && isBilibili(resource.url)" class="video-embed">
            <iframe :src="bilibiliEmbed(resource.url)" frameborder="0" scrolling="no" allowfullscreen></iframe>
          </div>
          <div v-else-if="resource.type === 'video' && isYoutube(resource.url)" class="video-embed">
            <iframe
              :src="youtubeEmbed(resource.url)"
              frameborder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
            ></iframe>
          </div>
          <a v-else-if="resource.url" :href="resource.url" target="_blank" class="resource-link">
            {{ resourceTypeLabel(resource.type) }} · {{ resource.title }}
          </a>
          <div v-else class="resource-inline">
            <span class="cat-tag">{{ resourceTypeLabel(resource.type) }}</span>
            <b>{{ resource.title }}</b>
            <small v-if="resource.description">{{ resource.description }}</small>
          </div>
        </div>
      </div>

      <div class="field" v-if="!resources.length && node.video_urls && node.video_urls.length">
        <div class="section-title">视频资源 <span>{{ node.video_urls.length }}</span></div>
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
          <a v-else :href="url" target="_blank" class="resource-link">打开视频 {{ idx + 1 }}</a>
        </div>
      </div>

      <div class="field" v-if="!resources.length && node.exercises && node.exercises.length">
        <div class="section-title">习题资源 <span>{{ node.exercises.length }}</span></div>
        <div v-for="(url, idx) in node.exercises" :key="'e' + idx" class="resource-item">
          <a :href="url" target="_blank" class="resource-link exercise-link">打开习题 {{ idx + 1 }}</a>
        </div>
      </div>

      <div class="field" v-if="neighbors.length">
        <div class="section-title">关联知识点 <span>{{ neighbors.length }}</span></div>
        <div
          v-for="nb in neighbors"
          :key="nb.node.id"
          class="node-item"
          @click="$emit('locate', nb.node)"
        >
          <span>{{ nb.node.name }}</span>
          <span class="cat-tag">{{ relationLabel(nb.relation.type) }}</span>
        </div>
      </div>

      <DiscussPanel :nodeId="node.id" :userId="userId" :userRole="userRole" />

      <div class="form-actions sticky-actions">
        <button class="secondary" @click="$emit('show-roadmap', node.id)">查看学习路径</button>
        <button @click="$emit('ask-ai', node)">问 AI</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { graphApi, resourceApi } from '../api/index.js'
import DiscussPanel from './DiscussPanel.vue'

const props = defineProps({
  node: { type: Object, default: null },
  userId: { type: String, default: '' },
  userRole: { type: String, default: 'student' },
})

defineEmits(['close', 'locate', 'show-roadmap', 'ask-ai'])

const neighbors = ref([])
const resources = ref([])

watch(() => props.node, async (val) => {
  if (val && val.id) {
    try {
      neighbors.value = await graphApi.getNeighbors(val.id)
    } catch {
      neighbors.value = []
    }
    try {
      resources.value = await resourceApi.listByKnowledge(val.id, { status: 'published' })
    } catch {
      resources.value = []
    }
  } else {
    neighbors.value = []
    resources.value = []
  }
}, { immediate: true })

function relationLabel(type) {
  return type === 'PREREQUISITE' ? '前置' : type === 'RELATED_TO' ? '相关' : '关联'
}

function resourceTypeLabel(type) {
  return {
    video: '视频',
    exercise: '练习',
    article: '文章',
    quiz: '测验',
    document: '文档',
    link: '链接',
    ai_prompt: 'AI 提示',
  }[type] || '资源'
}

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
