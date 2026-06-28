<template>
  <div class="admin-section behavior-dashboard">
    <div class="section-head">
      <h4>学习行为数据大屏</h4>
      <div class="admin-section-actions">
        <button class="secondary small" @click="$emit('reset-filters')">重置筛选</button>
        <button class="secondary small" @click="$emit('refresh')">刷新大屏</button>
      </div>
    </div>

    <div class="dashboard-filter-bar">
      <div class="form-row">
        <label>课程</label>
        <select v-model="filters.course_id" @change="$emit('refresh')">
          <option value="">全部课程</option>
          <option v-for="course in courses" :key="course.id" :value="course.id">{{ course.name }}</option>
        </select>
      </div>
      <div class="form-row">
        <label>年级</label>
        <select v-model="filters.grade" @change="$emit('refresh')">
          <option value="">全部年级</option>
          <option v-for="grade in grades" :key="grade" :value="grade">{{ grade }}</option>
        </select>
      </div>
      <div class="form-row">
        <label>班级</label>
        <select v-model="filters.class_id" @change="$emit('refresh')">
          <option value="">全部班级</option>
          <option v-for="cls in classes" :key="cls.id" :value="cls.id">{{ cls.name }}</option>
        </select>
      </div>
      <div class="form-row">
        <label>学科</label>
        <select v-model="filters.subject" @change="$emit('refresh')">
          <option value="">全部学科</option>
          <option v-for="subject in subjects" :key="subject" :value="subject">{{ subject }}</option>
        </select>
      </div>
      <div class="form-row">
        <label>时间</label>
        <select v-model.number="filters.days" @change="$emit('refresh')">
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
          <option :value="90">近 90 天</option>
          <option :value="180">近 180 天</option>
        </select>
      </div>
    </div>

    <div class="dashboard-config">
      <label v-for="item in configItems" :key="item.key" class="dashboard-toggle">
        <input v-model="config[item.key]" type="checkbox" />
        <span>{{ item.label }}</span>
      </label>
    </div>

    <div v-if="config.activity" class="qa-analytics-grid behavior-metric-grid">
      <div class="qa-analytics-item"><strong>{{ activity.qa_questions || 0 }}</strong><span>学生提问</span></div>
      <div class="qa-analytics-item"><strong>{{ activity.practice_attempts || 0 }}</strong><span>答题尝试</span></div>
      <div class="qa-analytics-item"><strong>{{ activity.error_records || 0 }}</strong><span>新增错题</span></div>
      <div class="qa-analytics-item"><strong>{{ activity.active_students || 0 }}</strong><span>活跃学生</span></div>
    </div>

    <div class="dashboard-panel-grid">
      <div v-if="config.heat" class="dashboard-panel wide">
        <div class="panel-title-row">
          <h5>知识点访问热度 TOP</h5>
          <span>{{ filters.days }} 天</span>
        </div>
        <div v-if="!knowledgeHeatTop.length" class="empty-state compact">暂无行为热度数据</div>
        <button
          v-for="node in knowledgeHeatTop"
          :key="node.node_id"
          class="heat-rank-row"
          @click="$emit('locate', node.node_id)"
        >
          <span class="heat-rank-name">{{ node.name }}</span>
          <span class="heat-rank-bar"><i :style="{ width: heatWidth(node.heat) }"></i></span>
          <b>{{ node.heat }}</b>
          <small>问 {{ node.qa_count }} · 练 {{ node.attempt_count }} · 错 {{ node.error_count }}</small>
        </button>
      </div>

      <div v-if="config.questions" class="dashboard-panel">
        <div class="panel-title-row">
          <h5>高频提问榜</h5>
          <span>AI 来源引用</span>
        </div>
        <div v-if="!questionTop.length" class="empty-state compact">暂无高频提问数据</div>
        <button v-for="node in questionTop" :key="node.node_id" class="compact-rank-row" @click="$emit('locate', node.node_id)">
          <span>{{ node.name }}</span>
          <b>{{ node.qa_count }}</b>
        </button>
      </div>

      <div v-if="config.errors" class="dashboard-panel">
        <div class="panel-title-row">
          <h5>错题高频考点</h5>
          <span>错题本</span>
        </div>
        <div v-if="!errorHotNodes.length" class="empty-state compact">暂无错题考点数据</div>
        <button v-for="node in errorHotNodes" :key="node.node_id" class="compact-rank-row danger" @click="$emit('locate', node.node_id)">
          <span>{{ node.name }}</span>
          <b>{{ node.error_count }}</b>
        </button>
      </div>

      <div v-if="config.weak" class="dashboard-panel">
        <div class="panel-title-row">
          <h5>班级薄弱分布</h5>
          <span>低掌握 + 错题</span>
        </div>
        <div v-if="!classWeakDistribution.length" class="empty-state compact">暂无班级薄弱数据</div>
        <div v-for="cls in classWeakDistribution" :key="cls.class_id" class="class-weak-row">
          <div>
            <strong>{{ cls.class_name }}</strong>
            <small>{{ cls.grade || '未分级' }} · {{ cls.subject || '未分科' }} · {{ cls.student_count || 0 }} 人</small>
          </div>
          <span>薄弱 {{ cls.weak_count || 0 }}</span>
          <b>{{ cls.avg_score || 0 }}</b>
        </div>
      </div>

      <div v-if="config.trend" class="dashboard-panel">
        <div class="panel-title-row">
          <h5>活跃统计</h5>
          <span>日趋势</span>
        </div>
        <div v-if="!dailyActivity.length" class="empty-state compact">暂无活跃趋势数据</div>
        <div v-for="day in dailyActivity" :key="day.date" class="daily-activity-row">
          <span>{{ day.date?.slice(5) }}</span>
          <i :style="{ width: activityWidth(day) }"></i>
          <small>问 {{ day.qa || 0 }} · 练 {{ day.attempts || 0 }} · 错 {{ day.errors || 0 }}</small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  filters: { type: Object, required: true },
  config: { type: Object, required: true },
  configItems: { type: Array, default: () => [] },
  courses: { type: Array, default: () => [] },
  grades: { type: Array, default: () => [] },
  classes: { type: Array, default: () => [] },
  subjects: { type: Array, default: () => [] },
  activity: { type: Object, default: () => ({}) },
  knowledgeHeatTop: { type: Array, default: () => [] },
  questionTop: { type: Array, default: () => [] },
  classWeakDistribution: { type: Array, default: () => [] },
  errorHotNodes: { type: Array, default: () => [] },
  dailyActivity: { type: Array, default: () => [] },
  heatWidth: { type: Function, required: true },
  activityWidth: { type: Function, required: true },
})

defineEmits(['refresh', 'reset-filters', 'locate'])
</script>
