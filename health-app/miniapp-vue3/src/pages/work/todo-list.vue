<template>
  <view class="page" :class="{ dark: isDark }">
    <view class="top-decoration"></view>
    <view class="container">
      <!-- 添加区域 -->
      <view class="add-card">
        <text class="card-title">📝 添加任务</text>
        <input
          class="add-input"
          v-model="newContent"
          placeholder="输入任务内容"
          placeholder-class="placeholder"
          @confirm="addTodo"
        />
        <view class="deadline-row">
          <text class="deadline-label">截止日期</text>
          <picker mode="date" :value="newDeadline" @change="onDeadlineChange">
            <view class="deadline-picker">
              <text :class="['deadline-text', !newDeadline && 'deadline-placeholder']">
                {{ newDeadline || '选择截止日期（可选）' }}
              </text>
              <text class="deadline-arrow">›</text>
            </view>
          </picker>
        </view>
        <button class="add-btn" :disabled="submitting" @click="addTodo">
          {{ submitting ? '添加中...' : '添加任务' }}
        </button>
      </view>

      <!-- 任务列表 -->
      <view class="list-card">
        <view class="list-header">
          <text class="list-title">任务列表</text>
          <text class="list-count">共 {{ todoList.length }} 项</text>
        </view>

        <view v-if="todoList.length === 0" class="empty-state">
          <text class="empty-icon">📋</text>
          <text class="empty-text">暂无任务，添加一条试试</text>
        </view>

        <view v-for="todo in todoList" :key="todo.id" class="todo-item">
          <view class="todo-main">
            <text class="todo-content">{{ todo.content }}</text>
            <view v-if="todo.deadline" class="todo-deadline" :class="deadlineClass(todo.deadline)">
              <text class="deadline-icon">⏰</text>
              <text class="deadline-value">{{ todo.deadline }}</text>
            </view>
          </view>
          <view class="todo-actions">
            <button class="action-btn done" @click="completeTodo(todo.id)">完成</button>
          </view>
        </view>
      </view>
    </view>

    <view v-if="loading" class="loading-mask">
      <view class="loading-content">加载中...</view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useThemeStore } from '@/store/theme'
import { workApi } from '@/utils/api'

const themeStore = useThemeStore()
const { isDark } = themeStore

const todoList = ref([])
const newContent = ref('')
const newDeadline = ref('')
const submitting = ref(false)
const loading = ref(false)

function onDeadlineChange(e) {
  newDeadline.value = e.detail.value
}

// 截止日期样式：已过期=红，今天=橙，未来=绿
function deadlineClass(deadline) {
  if (!deadline) return ''
  const today = new Date().toISOString().slice(0, 10)
  if (deadline < today) return 'overdue'
  if (deadline === today) return 'due-today'
  return 'upcoming'
}

async function loadTodos() {
  loading.value = true
  try {
    const todos = await workApi.getTodayTodos()
    const list = Array.isArray(todos) ? todos : (todos?.data && Array.isArray(todos.data) ? todos.data : [])
    todoList.value = list
      .map(item => ({
        id: item.id,
        content: item.content || item.title || '',
        deadline: item.deadline || ''
      }))
      .sort((a, b) => {
        if (!a.deadline && !b.deadline) return 0
        if (!a.deadline) return 1
        if (!b.deadline) return -1
        return new Date(a.deadline) - new Date(b.deadline)
      })
  } catch (error) {
    console.warn('加载TODO失败', error)
    todoList.value = []
  } finally {
    loading.value = false
  }
}

async function addTodo() {
  const content = newContent.value.trim()
  if (!content) {
    uni.showToast({ title: '请输入任务内容', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const result = await workApi.addTodayTodo(content, newDeadline.value || undefined)
    const newItem = result?.data || result || {}
    todoList.value.push({
      id: newItem.id ?? Date.now(),
      content: newItem.content || newItem.title || content,
      deadline: newItem.deadline || newDeadline.value || ''
    })
    // 重新排序
    todoList.value.sort((a, b) => {
      if (!a.deadline && !b.deadline) return 0
      if (!a.deadline) return 1
      if (!b.deadline) return -1
      return new Date(a.deadline) - new Date(b.deadline)
    })
    newContent.value = ''
    newDeadline.value = ''
    uni.showToast({ title: '添加成功', icon: 'success' })
    uni.$emit('todoRefresh')
  } catch (error) {
    console.warn('添加TODO失败', error)
    uni.showToast({ title: error.message || '添加失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

async function completeTodo(id) {
  uni.showModal({
    title: '确认完成',
    content: '确定将此任务标记为完成吗？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await workApi.completeTodo(id)
        todoList.value = todoList.value.filter(item => item.id !== id)
        uni.showToast({ title: '已完成', icon: 'success' })
        uni.$emit('todoRefresh')
      } catch (error) {
        console.warn('完成TODO失败', error)
        todoList.value = todoList.value.filter(item => item.id !== id)
        uni.showToast({ title: '已标记完成', icon: 'success' })
        uni.$emit('todoRefresh')
      }
    }
  })
}

onMounted(() => {
  loadTodos()
})
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  position: relative;
  overflow: hidden;
}

.top-decoration {
  position: absolute;
  top: -120rpx;
  right: -120rpx;
  width: 400rpx;
  height: 400rpx;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0));
}

.container {
  position: relative;
  z-index: 1;
  padding: 30rpx;
  padding-bottom: 80rpx;
}

/* 添加卡片 */
.add-card {
  background: var(--card-bg);
  border-radius: 36rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(16, 185, 129, 0.08);
  border: 1rpx solid rgba(16, 185, 129, 0.15);
}

.card-title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--text-primary);
  display: block;
  margin-bottom: 20rpx;
}

.add-input {
  height: 88rpx;
  background: var(--input-bg);
  border: 1.5px solid var(--input-border);
  border-radius: 24rpx;
  padding: 0 24rpx;
  font-size: 30rpx;
  color: var(--text-primary);
  margin-bottom: 16rpx;
}

.placeholder {
  color: var(--text-tertiary);
}

.deadline-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.deadline-label {
  font-size: 28rpx;
  color: var(--text-secondary);
  white-space: nowrap;
}

.deadline-picker {
  flex: 1;
  height: 80rpx;
  background: var(--input-bg);
  border: 1.5px solid var(--input-border);
  border-radius: 24rpx;
  padding: 0 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.deadline-text {
  font-size: 28rpx;
  color: var(--text-primary);
}

.deadline-placeholder {
  color: var(--text-tertiary);
}

.deadline-arrow {
  font-size: 32rpx;
  color: var(--text-tertiary);
}

.add-btn {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  background: linear-gradient(135deg, #10b981, #059669);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 600;
  border: none;
  border-radius: 48rpx;
}

.add-btn[disabled] {
  opacity: 0.6;
}

/* 列表卡片 */
.list-card {
  background: var(--card-bg);
  border-radius: 36rpx;
  padding: 32rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.05);
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.list-title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--text-primary);
}

.list-count {
  font-size: 26rpx;
  color: var(--text-tertiary);
}

.empty-state {
  text-align: center;
  padding: 60rpx 0;
}

.empty-icon {
  font-size: 64rpx;
  display: block;
  margin-bottom: 16rpx;
}

.empty-text {
  font-size: 28rpx;
  color: var(--text-tertiary);
}

.todo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  padding: 24rpx 0;
  border-bottom: 1rpx solid var(--divider);
}

.todo-item:last-child {
  border-bottom: none;
}

.todo-main {
  flex: 1;
  min-width: 0;
}

.todo-content {
  font-size: 30rpx;
  color: var(--text-primary);
  display: block;
  margin-bottom: 8rpx;
}

.todo-deadline {
  display: inline-flex;
  align-items: center;
  gap: 6rpx;
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
  font-size: 24rpx;
}

.todo-deadline.upcoming {
  background: rgba(34, 197, 94, 0.1);
  color: #15803d;
}

.todo-deadline.due-today {
  background: rgba(249, 115, 22, 0.1);
  color: #ea580c;
}

.todo-deadline.overdue {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.deadline-icon {
  font-size: 20rpx;
}

.todo-actions {
  flex-shrink: 0;
}

.action-btn {
  min-width: 120rpx;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 32rpx;
  font-size: 26rpx;
  font-weight: 600;
  border: none;
  padding: 0 24rpx;
}

.action-btn.done {
  background: #34d399;
  color: #ffffff;
}

.loading-mask {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

.loading-content {
  padding: 30rpx 40rpx;
  background: var(--modal-bg);
  border-radius: 24rpx;
  font-size: 28rpx;
  color: var(--text-primary);
}
</style>
