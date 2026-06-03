<template>
  <view class="container" :class="{ dark: isDark }">
    <view class="header-card">
      <text class="page-title">工作时长统计</text>
      <text class="page-sub">查看近期工作趋势与表现</text>
    </view>

    <view class="summary-card">
      <view class="summary-row">
        <text class="summary-label">今日工作时长</text>
        <text class="summary-value">{{ todayMinutes }}分钟</text>
      </view>
      <view class="summary-row">
        <text class="summary-label">今日专注时长</text>
        <text class="summary-value">{{ focusMinutes }}分钟</text>
      </view>
      <view class="summary-row">
        <text class="summary-label">今日番茄数</text>
        <text class="summary-value">{{ pomodoroSessions }}个</text>
      </view>
      <view class="progress-bar">
        <view class="progress-fill" :style="{ width: workPercent + '%' }"></view>
      </view>
      <text class="progress-hint">工作时长目标：{{ targetMinutes }}分钟（8小时）</text>
    </view>

    <view class="history-card">
      <view class="history-header">
        <view>
          <text class="history-title">工作时长历史统计</text>
          <text class="history-note">近期趋势与累计表现</text>
        </view>
      </view>

      <view class="history-stats-grid">
        <view class="history-item">
          <text class="item-label">累计工作</text>
          <text class="item-value">{{ summary.total }}分钟</text>
        </view>
        <view class="history-item">
          <text class="item-label">日均工作</text>
          <text class="item-value">{{ summary.avg }}分钟</text>
        </view>
        <view class="history-item">
          <text class="item-label">达标天数</text>
          <text class="item-value">{{ summary.goalDays }}天</text>
        </view>
        <view class="history-item">
          <text class="item-label">达标率</text>
          <text class="item-value">{{ summary.goalRate }}%</text>
        </view>
      </view>

      <view class="trend-section">
        <view class="trend-title-row">
          <text class="trend-title">最近7天趋势</text>
          <text class="trend-sub">按天展示</text>
        </view>
        <view class="trend-bars">
          <view v-for="(day, index) in historyDays" :key="index" class="trend-bar-item">
            <text class="bar-label">{{ day.label }}</text>
            <view class="bar-wrapper">
              <view class="bar" :style="{ height: day.barHeight + 'px' }"></view>
            </view>
            <text class="bar-value">{{ day.value }}</text>
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
import { ref, computed, onMounted } from 'vue'
import { useThemeStore } from '@/store/theme'
import { workApi } from '@/utils/api'

const themeStore = useThemeStore()
const { isDark } = themeStore

const todayMinutes = ref(0)
const focusMinutes = ref(0)
const pomodoroSessions = ref(0)
const targetMinutes = ref(480)
const summary = ref({ total: 0, avg: 0, goalDays: 0, goalRate: 0 })
const historyDays = ref([])
const loading = ref(false)

const workPercent = computed(() => {
  if (!targetMinutes.value) return 0
  return Math.min(100, Math.round((todayMinutes.value / targetMinutes.value) * 100))
})

async function loadData() {
  loading.value = true
  try {
    const [durationData, dailyStats, weeklyData] = await Promise.all([
      workApi.getTodayWorkDuration().catch(() => ({ durationMinutes: 0, workDuration: 0 })),
      workApi.getTodayStats().catch(() => ({ focusMinutes: 0, sessions: 0 })),
      workApi.getWeeklyStats().catch(() => [])
    ])

    todayMinutes.value = durationData?.durationMinutes ?? durationData?.workDuration ?? 0
    focusMinutes.value = typeof dailyStats?.focusMinutes === 'number' ? dailyStats.focusMinutes : 0
    const rawSessions = dailyStats?.sessions
    pomodoroSessions.value = Array.isArray(rawSessions) ? rawSessions.length : (typeof rawSessions === 'number' ? rawSessions : 0)

    // 处理周数据
    const weekly = Array.isArray(weeklyData) ? weeklyData : []
    const last7 = weekly.slice(-7)
    const maxValue = Math.max(...last7.map(d => d.minutes || d.durationMinutes || d.workMinutes || 0), 1)
    const chartHeight = 120

    historyDays.value = last7.map(day => {
      const value = day.minutes || day.durationMinutes || day.workMinutes || 0
      const date = new Date(day.date || day.day)
      const label = `${date.getMonth() + 1}/${date.getDate()}`
      const barHeight = Math.max(6, Math.round((value / maxValue) * chartHeight))
      return { label, value, barHeight }
    })

    const total = last7.reduce((sum, d) => sum + (d.minutes || d.durationMinutes || d.workMinutes || 0), 0)
    const avg = last7.length ? Math.round(total / last7.length) : 0
    const goalDays = last7.filter(d => (d.minutes || d.durationMinutes || d.workMinutes || 0) >= targetMinutes.value).length
    const goalRate = last7.length ? Math.round((goalDays / last7.length) * 100) : 0
    summary.value = { total, avg, goalDays, goalRate }
  } catch (error) {
    console.error('加载工作统计失败', error)
    uni.showToast({ title: error.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.container {
  padding: 30rpx;
  min-height: 100vh;
  background: var(--bg-primary);
}
.header-card {
  padding: 30rpx 30rpx 24rpx;
  margin-bottom: 24rpx;
  background: linear-gradient(135deg, #f97316, #fb923c);
  border-radius: 32rpx;
  color: white;
}
.page-title {
  font-size: 38rpx;
  font-weight: 800;
  line-height: 1.1;
}
.page-sub {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  opacity: 0.9;
}
.summary-card {
  background: var(--card-bg);
  border-radius: 32rpx;
  padding: 30rpx;
  box-shadow: 0 16rpx 34rpx rgba(249, 115, 22, 0.08);
  margin-bottom: 24rpx;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
}
.summary-label {
  color: var(--text-secondary);
  font-size: 28rpx;
}
.summary-value {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--text-primary);
}
.progress-bar {
  width: 100%;
  height: 16rpx;
  border-radius: 12rpx;
  background: #fef3e2;
  overflow: hidden;
  margin-top: 8rpx;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #f97316, #fb923c);
}
.progress-hint {
  display: block;
  margin-top: 10rpx;
  font-size: 22rpx;
  color: var(--text-tertiary);
  text-align: right;
}
.history-card {
  background: linear-gradient(135deg, #fff7ed, #fffbf5);
  border-radius: 32rpx;
  padding: 30rpx;
  box-shadow: 0 12rpx 28rpx rgba(249, 115, 22, 0.06);
}
.history-header {
  margin-bottom: 24rpx;
}
.history-title {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--text-primary);
}
.history-note {
  display: block;
  margin-top: 10rpx;
  font-size: 24rpx;
  color: var(--text-secondary);
}
.history-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18rpx;
  margin-bottom: 28rpx;
}
.history-item {
  background: var(--card-bg);
  border-radius: 24rpx;
  padding: 22rpx;
  box-shadow: 0 8rpx 18rpx rgba(0, 0, 0, 0.04);
}
.item-label {
  display: block;
  font-size: 24rpx;
  color: var(--text-tertiary);
  margin-bottom: 10rpx;
}
.item-value {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--text-primary);
}
.trend-section {
  background: var(--card-bg);
  border-radius: 28rpx;
  padding: 24rpx;
}
.trend-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}
.trend-title {
  font-size: 30rpx;
  font-weight: 700;
  color: var(--text-primary);
}
.trend-sub {
  font-size: 24rpx;
  color: var(--text-tertiary);
}
.trend-bars {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 10rpx;
  min-height: 160rpx;
}
.trend-bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.bar-wrapper {
  width: 100%;
  height: 120rpx;
  background: #fef3e2;
  border-radius: 20rpx;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  overflow: hidden;
}
.bar {
  width: 100%;
  max-width: 42rpx;
  background: linear-gradient(180deg, #f97316, #fb923c);
  border-radius: 20rpx 20rpx 8rpx 8rpx;
}
.bar-label {
  margin-top: 12rpx;
  font-size: 22rpx;
  color: var(--text-tertiary);
}
.bar-value {
  margin-top: 10rpx;
  font-size: 24rpx;
  color: var(--text-primary);
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
