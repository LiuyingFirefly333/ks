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

      <div v-if="canMarkMastery" class="mastery-mark-card">
        <div class="section-title">我的掌握度 <span>{{ masteryScore }} 分</span></div>
        <div class="mastery-mark-head">
          <span class="mastery-level-pill" :class="'level-' + masteryLevel">{{ masteryLevelLabel }}</span>
          <small v-if="node.mastery_score !== undefined">综合诊断 {{ node.mastery_score || 0 }} 分</small>
        </div>
        <input
          v-model.number="masteryScore"
          type="range"
          min="0"
          max="100"
          step="5"
          :disabled="savingMastery"
        />
        <div class="mastery-quick-actions">
          <button
            v-for="item in masteryPresets"
            :key="item.score"
            class="secondary"
            :class="{ active: masteryScore === item.score }"
            :disabled="savingMastery"
            @click="setMasteryScore(item.score)"
          >
            {{ item.label }}
          </button>
        </div>
        <div class="mastery-save-row">
          <button @click="saveMastery" :disabled="savingMastery || !hasMasteryChanged">
            {{ savingMastery ? '保存中...' : '保存掌握度' }}
          </button>
          <span v-if="masteryMessage">{{ masteryMessage }}</span>
        </div>
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
import { computed, ref, watch } from 'vue'
import { graphApi, recommendApi, resourceApi } from '../api/index.js'
import DiscussPanel from './DiscussPanel.vue'

const props = defineProps({
  node: { type: Object, default: null },
  userId: { type: String, default: '' },
  userRole: { type: String, default: 'student' },
})

const emit = defineEmits(['close', 'locate', 'show-roadmap', 'ask-ai', 'mastery-updated'])

const neighbors = ref([])
const resources = ref([])
const masteryScore = ref(0)
const savedMasteryScore = ref(0)
const savingMastery = ref(false)
const masteryMessage = ref('')

const masteryPresets = [
  { label: '未学', score: 0 },
  { label: '薄弱', score: 40 },
  { label: '一般', score: 70 },
  { label: '熟练', score: 90 },
]

const canMarkMastery = computed(() => props.userRole === 'student' && props.userId && props.node?.id)
const hasMasteryChanged = computed(() => Number(masteryScore.value) !== Number(savedMasteryScore.value))
const masteryLevel = computed(() => {
  if (masteryScore.value >= 85) return 'proficient'
  if (masteryScore.value >= 60) return 'fair'
  if (masteryScore.value > 0) return 'weak'
  return 'unlearned'
})
const masteryLevelLabel = computed(() => ({
  proficient: '熟练',
  fair: '一般',
  weak: '薄弱',
  unlearned: '未学习',
}[masteryLevel.value]))

watch(() => props.node, async (val) => {
  if (val && val.id) {
    const initialScore = Number(val.manual_score ?? val.mastery_score ?? 0)
    masteryScore.value = Number.isFinite(initialScore) ? initialScore : 0
    savedMasteryScore.value = masteryScore.value
    masteryMessage.value = ''
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
    masteryScore.value = 0
    savedMasteryScore.value = 0
    masteryMessage.value = ''
  }
}, { immediate: true })

function setMasteryScore(score) {
  masteryScore.value = score
}

async function saveMastery() {
  if (!canMarkMastery.value) return
  savingMastery.value = true
  masteryMessage.value = ''
  try {
    const score = Math.max(0, Math.min(100, Number(masteryScore.value) || 0))
    await recommendApi.setMastery(props.userId, props.node.id, score)
    savedMasteryScore.value = score
    masteryScore.value = score
    masteryMessage.value = '已更新'
    emit('mastery-updated', { node_id: props.node.id, score })
  } catch (err) {
    masteryMessage.value = err.normalizedMessage || '保存失败'
  } finally {
    savingMastery.value = false
  }
}

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
