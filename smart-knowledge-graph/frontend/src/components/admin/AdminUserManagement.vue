<template>
  <div class="admin-section">
    <div class="section-head">
      <h4>用户管理</h4>
      <div class="admin-section-actions">
        <button class="secondary small" @click="$emit('trigger-import')">导入 CSV</button>
        <button class="secondary small" @click="$emit('export-users')">导出 CSV</button>
        <input ref="importInputRef" type="file" accept=".csv,text/csv" class="hidden-file-input" @change="$emit('import-users', $event)" />
      </div>
    </div>

    <div class="admin-user-form">
      <div class="form-row">
        <label>姓名</label>
        <input v-model.trim="createForm.name" placeholder="例如：王同学" />
      </div>
      <div class="form-row">
        <label>邮箱</label>
        <input v-model.trim="createForm.email" type="email" placeholder="name@example.com" />
      </div>
      <div class="form-row">
        <label>初始密码</label>
        <input v-model="createForm.password" type="password" placeholder="至少 6 位" />
      </div>
      <div class="form-row">
        <label>角色</label>
        <select v-model="createForm.role">
          <option v-for="role in roles" :key="role.value" :value="role.value">{{ role.label }}</option>
        </select>
      </div>
      <button @click="$emit('create-user')" :disabled="loading || !canCreate">新增账号</button>
    </div>

    <div v-if="message" class="inline-hint">{{ message }}</div>
    <div v-if="error" class="inline-error">{{ error }}</div>

    <div v-if="users.length === 0" class="empty-state compact">暂无用户</div>
    <div v-else class="admin-user-table">
      <div class="admin-user-table-head">
        <span>账号</span>
        <span>邮箱</span>
        <span>角色</span>
        <span>状态</span>
        <span>操作</span>
      </div>
      <div v-for="u in users" :key="u.role + '-' + u.id" class="admin-user-row" :class="{ disabled: u.disabled }">
        <div class="admin-user-main">
          <strong>{{ u.name }}</strong>
          <small>{{ formatDate(u.created_at) || u.id }}</small>
        </div>
        <span class="admin-user-email">{{ u.email }}</span>
        <select class="admin-role-select" :value="u.role" :disabled="loading || u.disabled" @change="$emit('assign-role', u, $event.target.value)">
          <option v-for="role in roles" :key="role.value" :value="role.value">{{ role.label }}</option>
        </select>
        <span class="admin-status-badge" :class="{ disabled: u.disabled }">{{ u.disabled ? '已禁用' : '正常' }}</span>
        <button
          class="admin-disable-btn"
          :disabled="loading || u.disabled"
          @click="$emit('disable-user', u.role, u.id)"
        >
          禁用
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  users: { type: Array, default: () => [] },
  roles: { type: Array, default: () => [] },
  createForm: { type: Object, required: true },
  canCreate: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  message: { type: String, default: '' },
  error: { type: String, default: '' },
  formatDate: { type: Function, required: true },
})

defineEmits(['trigger-import', 'export-users', 'import-users', 'create-user', 'assign-role', 'disable-user'])

const importInputRef = ref(null)

defineExpose({
  openImportDialog: () => importInputRef.value?.click(),
})
</script>
