<template>
  <view class="container">
    <view class="header-card">
      <text class="page-title">{{ pageTitle }}</text>
      <text class="page-sub">{{ pageSub }}</text>
    </view>

    <view class="summary-card">
      <view class="summary-row">
        <text class="summary-label">今日{{ metricText }}</text>
        <text class="summary-value">{{ todayValue }}{{ unit }}</text>
      </view>
      <view class="summary-row">
        <text class="summary-label">目标</text>
        <text class="summary-value">{{ targetValue }}{{ unit }}</text>
      </view>
      <view class="progress-bar">
        <view class="progress-fill" :style="{ width: progressPercent + '%' }"></view>
      </view>
    </view>

    <view class="history-card">
      <view class="history-header">
        <view>
          <text class="history-title">{{ metricText }}历史统计</text>
          <text class="history-note">近期趋势与累计表现</text>
        </view>
      </view>

      <view class="history-stats-grid">
        <view class="history-item">
          <text class="item-label">累计{{ metricText }}</text>
          <text class="item-value">{{ summary.total }}{{ unit }}</text>
        </view>
        <view class="history-item">
          <text class="item-label">日均{{ metricText }}</text>
          <text class="item-value">{{ summary.avg }}{{ unit }}</text>
        </view>
        <view class="history-item">
          <text class="item-label">目标达标天数</text>
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
import { statsApi } from '@/utils/api'

const metric = ref('workout')
const pageTitle = ref('')
const pageSub = ref('')
const metricText = ref('')
const unit = ref('')
const todayValue = ref(0)
const targetValue = ref(0)
const summary = ref({ total: 0, avg: 0, goalDays: 0, goalRate: 0 })
const historyDays = ref([])
const loading = ref(false)

const metricMeta = {
  workout: {
    title: '运动历史',
    text: '运动',
    unit: '分钟',
    targetDefault: 30,
    historyField: 'workoutMinutes'
  },
  sleep: {
    title: '睡眠历史',
    text: '睡眠',
    unit: '小时',
    targetDefault: 8,
    historyField: 'sleepHours'
  },
  diet: {
    title: '饮食历史',
    text: '饮食',
    unit: '千卡',
    targetDefault: 2000,
    historyField: 'dietCalories'
  },
  steps: {
    title: '步数历史',
    text: '步数',
    unit: '步',
    targetDefault: 10000,
    historyField: 'steps'
  }
}

const progressPercent = computed(() => {
  if (!targetValue.value) return 0
  return Math.min(100, Math.round((todayValue.value / targetValue.value) * 100))
})

const summaryValue = computed(() => summary.value.total)

function getQueryOptions() {
  return (typeof getCurrentPages === 'function' && getCurrentPages().slice(-1)[0]?.options) || {}
}

function getMetricField(day) {
  const field = metricMeta[metric.value]?.historyField || 'workoutMinutes'
  return day[field] || 0
}

function buildHistoryItems(history) {
  const last7 = Array.isArray(history) ? history.slice(-7) : []
  const maxValue = Math.max(...last7.map((day) => getMetricField(day)), 1)
  const chartHeight = 120
  historyDays.value = last7.map((day) => {
    const value = getMetricField(day)
    const date = new Date(day.date)
    const label = `${date.getMonth() + 1}/${date.getDate()}`
    const barHeight = Math.max(6, Math.round((value / maxValue) * chartHeight))
    return { label, value, barHeight }
  })
  const total = last7.reduce((sum, day) => sum + getMetricField(day), 0)
  const avg = last7.length ? Math.round(total / last7.length) : 0
  const goalDays = last7.filter((day) => getMetricField(day) >= targetValue.value).length
  const goalRate = last7.length ? Math.round((goalDays / last7.length) * 100) : 0
  summary.value = { total, avg, goalDays, goalRate }
}

async function loadHistoryData() {
  loading.value = true
  try {
    const query = getQueryOptions()
    metric.value = query.metric || 'workout'
    const meta = metricMeta[metric.value] || metricMeta.workout

    pageTitle.value = `${meta.text}历史统计`
    pageSub.value = `查看最近30天的${meta.text}趋势与表现`
    metricText.value = meta.text
    unit.value = meta.unit

    if (metric.value === 'sleep') {
      const sleepTodayData = await statsApi.sleepToday()
      const sleepHours = Array.isArray(sleepTodayData.records)
        ? sleepTodayData.records.reduce((sum, r) => sum + (r.durationHours || 0), 0)
        : 0
      todayValue.value = sleepHours
      targetValue.value = sleepTodayData.targetHours ?? meta.targetDefault
    } else if (metric.value === 'diet') {
      const dietTodayData = await statsApi.dietToday()
      todayValue.value = dietTodayData.totalCalories ?? 0
      targetValue.value = dietTodayData.targetCalories ?? meta.targetDefault
    } else {
      const todayData = await statsApi.today()
      if (metric.value === 'steps') {
        todayValue.value = todayData.steps ?? 0
        targetValue.value = todayData.stepsTarget ?? meta.targetDefault
      } else {
        todayValue.value = todayData.completedMinutes ?? 0
        targetValue.value = todayData.targetMinutes ?? meta.targetDefault
      }
    }

    const history = await statsApi.getHistory({ days: 30 })
    buildHistoryItems(history)
  } catch (error) {
    console.error('加载历史统计失败', error)
    uni.showToast({ title: error.message || '加载历史失败', icon: 'none' })
    historyDays.value = []
    summary.value = { total: 0, avg: 0, goalDays: 0, goalRate: 0 }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadHistoryData()
})
</script>

<style scoped>
.container {
  padding: 30rpx;
  min-height: 100vh;
  background: #f7fbff;
}
.header-card {
  padding: 30rpx 30rpx 24rpx;
  margin-bottom: 24rpx;
  background: linear-gradient(135deg, #409eff, #69c0ff);
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
  background: white;
  border-radius: 32rpx;
  padding: 30rpx;
  box-shadow: 0 16rpx 34rpx rgba(31, 81, 133, 0.08);
  margin-bottom: 24rpx;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
}
.summary-label {
  color: #5c6f8a;
  font-size: 28rpx;
}
.summary-value {
  font-size: 34rpx;
  font-weight: 700;
  color: #1f2e4a;
}
.progress-bar {
  width: 100%;
  height: 16rpx;
  border-radius: 12rpx;
  background: #f2f6ff;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #69c0ff);
}
.history-card {
  background: linear-gradient(135deg, #e8f7ff, #f8fcff);
  border-radius: 32rpx;
  padding: 30rpx;
  box-shadow: 0 12rpx 28rpx rgba(47, 86, 144, 0.08);
}
.history-header {
  margin-bottom: 24rpx;
}
.history-title {
  font-size: 34rpx;
  font-weight: 700;
  color: #1f3a6f;
}
.history-note {
  display: block;
  margin-top: 10rpx;
  font-size: 24rpx;
  color: #5c718f;
}
.history-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18rpx;
  margin-bottom: 28rpx;
}
.history-item {
  background: white;
  border-radius: 24rpx;
  padding: 22rpx;
  box-shadow: 0 8rpx 18rpx rgba(0, 0, 0, 0.04);
}
.item-label {
  display: block;
  font-size: 24rpx;
  color: #7b8ea0;
  margin-bottom: 10rpx;
}
.item-value {
  font-size: 32rpx;
  font-weight: 700;
  color: #1f2e4a;
}
.trend-section {
  background: white;
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
  color: #1a3a6f;
}
.trend-sub {
  font-size: 24rpx;
  color: #7b8ea0;
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
  background: #f4f7ff;
  border-radius: 20rpx;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  overflow: hidden;
}
.bar {
  width: 100%;
  max-width: 42rpx;
  background: linear-gradient(180deg, #409eff, #7cc1ff);
  border-radius: 20rpx 20rpx 8rpx 8rpx;
}
.bar-label {
  margin-top: 12rpx;
  font-size: 22rpx;
  color: #7b8ea0;
}
.bar-value {
  margin-top: 10rpx;
  font-size: 24rpx;
  color: #1f2e4a;
}
.loading-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}
.loading-content {
  padding: 30rpx 40rpx;
  background: white;
  border-radius: 24rpx;
  font-size: 28rpx;
  color: #1f2e4a;
}
</style>
