<template>
  <div class="profile-center">
    <section class="profile-hero">
      <div class="profile-avatar" :style="{ backgroundImage: avatarStyle }">
        <span v-if="!form.avatar_url">{{ initials }}</span>
      </div>
      <div class="profile-hero-main">
        <div class="profile-kicker">{{ roleText }}</div>
        <h2>{{ displayName }}</h2>
        <p>{{ form.bio || '记录学习轨迹、掌握情况和个人资料。' }}</p>
      </div>
      <button class="soft-button" @click="loadAll">刷新</button>
    </section>

    <div class="profile-grid">
      <section class="profile-card profile-form-card">
        <div class="section-head">
          <h3>个人资料</h3>
          <span v-if="savedText" class="save-hint">{{ savedText }}</span>
        </div>

        <div class="form-row">
          <label>昵称 / 姓名</label>
          <input v-model="form.name" placeholder="请输入昵称" />
        </div>
        <div class="form-row">
          <label>头像 URL</label>
          <input v-model="form.avatar_url" placeholder="https://..." />
        </div>
        <div class="form-row">
          <label>个人简介</label>
          <textarea v-model="form.bio" rows="4" placeholder="写一句你的学习目标或教学签名" />
        </div>
        <button class="full-width" :disabled="saving || !form.name.trim()" @click="saveProfile">
          {{ saving ? '保存中...' : '保存资料' }}
        </button>
      </section>

      <section class="profile-card">
        <div class="section-head">
          <h3>学习情况概览</h3>
          <span class="profile-date">{{ todayText }}</span>
        </div>

        <div class="profile-stats-grid">
          <div v-for="item in overviewItems" :key="item.label" class="profile-stat">
            <strong>{{ item.value }}</strong>
            <span>{{ item.label }}</span>
          </div>
        </div>

        <div v-if="isStudent" class="mastery-bars">
          <div v-for="item in masteryItems" :key="item.key" class="mastery-bar-row">
            <span>{{ item.label }}</span>
            <div class="mastery-track">
              <i :style="{ width: item.percent + '%', background: item.color }"></i>
            </div>
            <b>{{ item.count }}</b>
          </div>
        </div>
      </section>
    </div>

    <div v-if="isStudent" class="profile-grid lower">
      <section class="profile-card">
        <div class="section-head">
          <h3>薄弱知识点</h3>
          <span>{{ weakNodes.length }} 项</span>
        </div>
        <div v-if="!weakNodes.length" class="empty-state compact">暂无薄弱项，继续保持。</div>
        <div v-else class="profile-node-list">
          <button
            v-for="node in weakNodes"
            :key="node.node_id"
            class="profile-node-item"
            @click="$emit('locate', node.node_id)"
          >
            <span>{{ node.name }}</span>
            <small>{{ node.category || '未分类' }} · {{ node.score }} 分</small>
          </button>
        </div>
      </section>

      <section class="profile-card">
        <div class="section-head">
          <h3>近期掌握较好</h3>
          <span>{{ recentMastery.length }} 项</span>
        </div>
        <div v-if="!recentMastery.length" class="empty-state compact">还没有掌握度记录。</div>
        <div v-else class="profile-node-list">
          <button
            v-for="node in recentMastery"
            :key="node.node_id"
            class="profile-node-item success"
            @click="$emit('locate', node.node_id)"
          >
            <span>{{ node.name }}</span>
            <small>{{ node.category || '未分类' }} · {{ node.score }} 分</small>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { profileApi } from '../api/index.js'

const props = defineProps({
  user: { type: Object, default: null },
  courseId: { type: String, default: '' },
})
const emit = defineEmits(['updated', 'locate'])

const form = reactive({ name: '', avatar_url: '', bio: '' })
const stats = ref(null)
const saving = ref(false)
const savedText = ref('')

const roleText = computed(() => ({ student: '学生', teacher: '教师', admin: '管理员' }[props.user?.role] || '用户'))
const displayName = computed(() => form.name || props.user?.name || '未命名用户')
const initials = computed(() => displayName.value.slice(0, 2).toUpperCase())
const avatarStyle = computed(() => form.avatar_url ? `url("${form.avatar_url}")` : 'none')
const isStudent = computed(() => (props.user?.role || stats.value?.role) === 'student')
const todayText = computed(() => new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' }))
const weakNodes = computed(() => stats.value?.weak_nodes || [])
const recentMastery = computed(() => stats.value?.recent_mastery || [])

const masteryItems = computed(() => {
  const summary = stats.value?.mastery_summary || {}
  const total = Math.max(Object.values(summary).reduce((sum, count) => sum + Number(count || 0), 0), 1)
  return [
    { key: 'proficient', label: '熟练', color: '#16a34a' },
    { key: 'fair', label: '一般', color: '#f59e0b' },
    { key: 'weak', label: '薄弱', color: '#f97316' },
    { key: 'unlearned', label: '未学习', color: '#94a3b8' },
  ].map(item => {
    const count = summary[item.key] || 0
    return { ...item, count, percent: Math.round((count / total) * 100) }
  })
})

const overviewItems = computed(() => {
  const overview = stats.value?.overview || {}
  if (isStudent.value) {
    return [
      { label: '平均掌握度', value: `${overview.average_score || 0} 分` },
      { label: '学习进度', value: `${Math.round((overview.completion_rate || 0) * 100)}%` },
      { label: 'AI 提问', value: overview.qa_questions || 0 },
      { label: '错题记录', value: overview.error_count || 0 },
    ]
  }
  if (props.user?.role === 'teacher') {
    return [
      { label: '管理课程', value: overview.course_count || 0 },
      { label: '授课班级', value: overview.class_count || 0 },
      { label: '覆盖学生', value: overview.student_count || 0 },
      { label: '本月目标', value: '教研' },
    ]
  }
  return [
    { label: '知识点', value: overview.total_nodes || 0 },
    { label: '课程', value: overview.course_count || 0 },
    { label: '学生', value: overview.student_count || 0 },
    { label: '教师', value: overview.teacher_count || 0 },
  ]
})

function fillProfile(profile) {
  form.name = profile?.name || props.user?.name || ''
  form.avatar_url = profile?.avatar_url || props.user?.avatar_url || ''
  form.bio = profile?.bio || props.user?.bio || ''
}

async function loadProfile() {
  const data = await profileApi.get()
  fillProfile(data.profile)
  emit('updated', { ...data.profile, role: data.role })
}

async function loadStats() {
  stats.value = await profileApi.stats(props.courseId || undefined)
}

async function loadAll() {
  try {
    await Promise.all([loadProfile(), loadStats()])
  } catch (err) {
    savedText.value = err.normalizedMessage || '加载失败'
  }
}

async function saveProfile() {
  saving.value = true
  savedText.value = ''
  try {
    const data = await profileApi.update({
      name: form.name.trim(),
      avatar_url: form.avatar_url.trim(),
      bio: form.bio.trim(),
    })
    fillProfile(data.profile)
    emit('updated', { ...data.profile, role: data.role })
    savedText.value = '已保存'
  } catch (err) {
    savedText.value = err.normalizedMessage || '保存失败'
  } finally {
    saving.value = false
  }
}

watch(() => props.user, user => fillProfile(user), { immediate: true, deep: true })
watch(() => props.courseId, () => loadStats())

onMounted(loadAll)
</script>
