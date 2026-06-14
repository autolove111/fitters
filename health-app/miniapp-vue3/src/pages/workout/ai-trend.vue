<template>
  <view class="trend-page">
    <view class="hero">
      <view>
        <text class="hero-kicker">Fitters Pro</text>
        <text class="hero-title">30天私人顾问报告</text>
        <text class="hero-subtitle">把运动、睡眠、饮食放在一起看，找到真正影响训练状态的原因。</text>
      </view>
      <view class="hero-badge">
        <text class="hero-badge-value">{{ chartItems.length }}</text>
        <text class="hero-badge-label">天记录</text>
      </view>
    </view>

    <view class="summary-panel">
      <text class="section-title">顾问结论</text>
      <text class="coach-summary">{{ localizeAiPlanText(trendAnalysis.coachSummary || fallbackSummary) }}</text>
      <view class="metric-grid">
        <view v-for="(item, index) in displayMetrics" :key="'metric-' + index" class="metric-card" :class="item.tone">
          <text class="metric-value">{{ item.value }}</text>
          <text class="metric-label">{{ item.label }}</text>
        </view>
      </view>
    </view>

    <view class="chart-panel">
      <view class="section-head">
        <view>
          <text class="section-title">30天趋势图</text>
        </view>
      </view>
      <scroll-view class="chart-scroll" scroll-x>
        <view class="chart-track" :style="{ gridTemplateColumns: `repeat(${chartItems.length || 1}, minmax(0, 1fr))` }">
          <view v-for="(item, index) in chartItems" :key="'chart-' + index" class="day-column">
            <view class="day-bars">
              <view class="bar workout" :style="{ height: workoutBarHeight(item.workoutMinutes) + '%' }"></view>
              <view class="bar sleep" :style="{ height: sleepBarHeight(item.sleepHours) + '%' }"></view>
              <view class="bar diet" :style="{ height: dietBarHeight(item.dietCalories) + '%' }"></view>
            </view>
            <text class="day-label">{{ item.label || formatLabel(item.date, index) }}</text>
          </view>
        </view>
      </scroll-view>
      <view class="legend-row">
        <text class="legend workout-dot">运动</text>
        <text class="legend sleep-dot">睡眠</text>
        <text class="legend diet-dot">饮食稳定</text>
      </view>
    </view>

    <view class="day-list-panel">
      <view class="section-head">
        <view>
          <text class="section-title">逐日记录</text>
        </view>
      </view>
      <view v-for="(item, index) in chartItems" :key="'day-' + index" class="day-card">
        <view class="day-card-head">
          <text class="day-card-title">第{{ index + 1 }}天 · {{ item.label || formatLabel(item.date, index) }}</text>
          <text class="day-status" :class="dayStatus(item).tone">{{ dayStatus(item).text }}</text>
        </view>
        <view class="day-values">
          <view class="day-value">
            <text class="value-number">{{ numberText(item.workoutMinutes) }}</text>
            <text class="value-label">运动分钟</text>
          </view>
          <view class="day-value">
            <text class="value-number">{{ numberText(item.sleepHours) }}</text>
            <text class="value-label">睡眠小时</text>
          </view>
          <view class="day-value">
            <text class="value-number">{{ numberText(item.dietCalories) }}</text>
            <text class="value-label">饮食千卡</text>
          </view>
        </view>
      </view>
    </view>

    <view v-if="loading" class="loading-mask">
      <view class="loading-content">正在加载30天数据...</view>
    </view>
  </view>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { statsApi } from '@/utils/api'
import { localizeAiPlanText } from '@/utils/aiPlanFormatter.mjs'

const loading = ref(false)
const trendAnalysis = ref({
  coachSummary: '',
  metrics: [],
  chart: [],
  windowDays: 0
})

const fallbackSummary = '连续记录越完整，私人顾问越能看出你的训练节奏、恢复状态和饮食波动。'

const chartItems = computed(() => (Array.isArray(trendAnalysis.value.chart) ? trendAnalysis.value.chart.slice(-30) : []))
const displayMetrics = computed(() => {
  if (Array.isArray(trendAnalysis.value.metrics) && trendAnalysis.value.metrics.length) {
    return trendAnalysis.value.metrics
  }
  const items = chartItems.value
  const activeDays = items.filter((item) => Number(item.workoutMinutes) >= 20).length
  const sleepGoodDays = items.filter((item) => Number(item.sleepHours) >= 7).length
  const dietStableDays = items.filter((item) => {
    const calories = Number(item.dietCalories) || 0
    return calories >= 1700 && calories <= 2200
  }).length
  const avgWorkout = items.length
    ? Math.round(items.reduce((sum, item) => sum + (Number(item.workoutMinutes) || 0), 0) / items.length)
    : 0
  return [
    { label: '活跃训练日', value: `${activeDays}/${items.length}天`, tone: activeDays >= 12 ? 'good' : 'warn' },
    { label: '平均运动', value: `${avgWorkout}分钟/天`, tone: avgWorkout >= 25 ? 'good' : 'warn' },
    { label: '睡眠达标', value: `${sleepGoodDays}/${items.length}天`, tone: sleepGoodDays >= 14 ? 'good' : 'warn' },
    { label: '饮食稳定', value: `${dietStableDays}/${items.length}天`, tone: dietStableDays >= 14 ? 'good' : 'warn' }
  ]
})

function numberText(value) {
  const number = Number(value) || 0
  return Number.isInteger(number) ? String(number) : number.toFixed(1)
}

function formatLabel(date, index) {
  if (!date) return `D${index + 1}`
  const parsed = new Date(date)
  if (Number.isNaN(parsed.getTime())) return String(date).slice(5) || `D${index + 1}`
  return `${parsed.getMonth() + 1}/${parsed.getDate()}`
}

function workoutBarHeight(value) {
  return Math.max(8, Math.min(100, Math.round((Number(value) || 0) / 60 * 100)))
}

function sleepBarHeight(value) {
  return Math.max(8, Math.min(100, Math.round((Number(value) || 0) / 9 * 100)))
}

function dietBarHeight(value) {
  const calories = Number(value) || 0
  if (!calories) return 8
  const distance = Math.min(900, Math.abs(calories - 2000))
  return Math.max(12, Math.round((1 - distance / 900) * 100))
}

function dayStatus(item) {
  const workoutOk = Number(item.workoutMinutes) >= 20
  const sleepOk = Number(item.sleepHours) >= 7
  const calories = Number(item.dietCalories) || 0
  const dietOk = calories >= 1700 && calories <= 2200
  const score = [workoutOk, sleepOk, dietOk].filter(Boolean).length
  if (score >= 3) return { text: '状态很好', tone: 'good' }
  if (score === 2) return { text: '基本稳定', tone: 'mid' }
  return { text: '需要调整', tone: 'warn' }
}

function buildTrendFromHistory(history) {
  const list = Array.isArray(history) ? history.slice(-30) : []
  trendAnalysis.value = {
    coachSummary: list.length
      ? `已读取最近${list.length}天记录，Pro 会把训练、恢复和饮食一起看，再给出更像私人教练的安排。`
      : fallbackSummary,
    metrics: [],
    chart: list.map((item, index) => ({
      label: formatLabel(item.date, index),
      date: item.date,
      workoutMinutes: Number(item.workoutMinutes) || 0,
      sleepHours: Number(item.sleepHours) || 0,
      dietCalories: Number(item.dietCalories) || 0
    })),
    windowDays: list.length
  }
}

async function loadTrendDetail() {
  const cached = uni.getStorageSync('ai_trend_analysis')
  if (cached?.chart?.length) {
    trendAnalysis.value = cached
    return
  }

  loading.value = true
  try {
    const history = await statsApi.getHistory({ days: 30 })
    buildTrendFromHistory(history)
  } catch (error) {
    uni.showToast({ title: error.message || '加载30天数据失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadTrendDetail()
})
</script>

<style scoped>
.trend-page {
  min-height: 100vh;
  padding: 28rpx;
  padding-bottom: 80rpx;
  background: #f4f8f5;
}
.hero {
  display: flex;
  justify-content: space-between;
  gap: 22rpx;
  padding: 34rpx;
  border-radius: 30rpx;
  color: #ffffff;
  background: linear-gradient(135deg, #0f5f49 0%, #1f7a5c 55%, #9bdc63 100%);
  box-shadow: 0 20rpx 42rpx rgba(31, 122, 92, 0.24);
}
.hero-kicker,
.hero-title,
.hero-subtitle,
.hero-badge-value,
.hero-badge-label,
.section-title,
.coach-summary,
.metric-value,
.metric-label,
.day-label,
.legend,
.day-card-title,
.day-status,
.value-number,
.value-label {
  display: block;
}
.hero-kicker {
  font-size: 22rpx;
  font-weight: 800;
  opacity: 0.86;
}
.hero-title {
  margin-top: 8rpx;
  font-size: 42rpx;
  font-weight: 900;
  line-height: 1.15;
}
.hero-subtitle {
  max-width: 500rpx;
  margin-top: 14rpx;
  font-size: 25rpx;
  line-height: 1.45;
  opacity: 0.92;
}
.hero-badge {
  width: 122rpx;
  height: 122rpx;
  flex: 0 0 122rpx;
  border-radius: 30rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.18);
  border: 1rpx solid rgba(255, 255, 255, 0.28);
}
.hero-badge-value {
  font-size: 42rpx;
  font-weight: 900;
  line-height: 1;
}
.hero-badge-label {
  margin-top: 8rpx;
  font-size: 20rpx;
  opacity: 0.86;
}
.summary-panel,
.chart-panel,
.day-list-panel {
  margin-top: 24rpx;
  padding: 26rpx;
  border-radius: 26rpx;
  background: #ffffff;
  box-shadow: 0 14rpx 34rpx rgba(31, 81, 66, 0.08);
}
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
  align-items: flex-start;
}
.section-title {
  color: #12382f;
  font-size: 30rpx;
  font-weight: 900;
}
.coach-summary {
  margin-top: 12rpx;
  color: #425466;
  font-size: 25rpx;
  line-height: 1.5;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14rpx;
  margin-top: 20rpx;
}
.metric-card {
  padding: 20rpx 16rpx;
  border-radius: 18rpx;
  background: #eef7f3;
}
.metric-card.warn {
  background: #fff3de;
}
.metric-value {
  color: #12382f;
  font-size: 30rpx;
  font-weight: 900;
}
.metric-label {
  margin-top: 6rpx;
  color: #667681;
  font-size: 22rpx;
}
.chart-scroll {
  width: 100%;
  margin-top: 22rpx;
}
.chart-track {
  width: 100%;
  height: 250rpx;
  display: grid;
  align-items: flex-end;
  gap: 6rpx;
  padding: 18rpx 44rpx 12rpx;
  border-radius: 22rpx;
  background:
    repeating-linear-gradient(to top, transparent 0, transparent 55rpx, rgba(18, 56, 47, 0.06) 56rpx),
    #f7faf8;
}
.day-column {
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
}
.day-bars {
  height: 190rpx;
  display: flex;
  align-items: flex-end;
  gap: 3rpx;
}
.bar {
  width: 7rpx;
  min-height: 8rpx;
  border-radius: 999rpx 999rpx 0 0;
}
.bar.workout {
  background: #1f7a5c;
}
.bar.sleep {
  background: #5ba7ff;
}
.bar.diet {
  background: #f0aa3a;
}
.day-label {
  min-height: 28rpx;
  margin-top: 8rpx;
  color: #71808c;
  font-size: 13rpx;
  line-height: 1.05;
  white-space: nowrap;
  text-align: center;
  transform: scale(0.92);
  transform-origin: center top;
}
.legend-row {
  display: flex;
  justify-content: center;
  gap: 28rpx;
  margin-top: 18rpx;
}
.legend {
  color: #536171;
  font-size: 22rpx;
}
.legend::before {
  content: '';
  display: inline-block;
  width: 14rpx;
  height: 14rpx;
  margin-right: 8rpx;
  border-radius: 50%;
}
.workout-dot::before {
  background: #1f7a5c;
}
.sleep-dot::before {
  background: #5ba7ff;
}
.diet-dot::before {
  background: #f0aa3a;
}
.day-card {
  margin-top: 16rpx;
  padding: 20rpx;
  border-radius: 22rpx;
  background: #f8fbf9;
  border: 1rpx solid #e7f0ec;
}
.day-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16rpx;
}
.day-card-title {
  color: #12382f;
  font-size: 26rpx;
  font-weight: 900;
}
.day-status {
  flex-shrink: 0;
  padding: 6rpx 12rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
  font-weight: 900;
}
.day-status.good {
  color: #0f6b4d;
  background: #def7c7;
}
.day-status.mid {
  color: #815a09;
  background: #fff0c8;
}
.day-status.warn {
  color: #9a3d24;
  background: #ffe3d8;
}
.day-values {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
  margin-top: 16rpx;
}
.day-value {
  padding: 14rpx 8rpx;
  border-radius: 16rpx;
  text-align: center;
  background: #ffffff;
}
.value-number {
  color: #12382f;
  font-size: 26rpx;
  font-weight: 900;
}
.value-label {
  margin-top: 4rpx;
  color: #77858f;
  font-size: 19rpx;
}
.loading-mask {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(244, 248, 245, 0.72);
  z-index: 99;
}
.loading-content {
  padding: 24rpx 34rpx;
  border-radius: 22rpx;
  color: #12382f;
  background: #ffffff;
  box-shadow: 0 14rpx 34rpx rgba(31, 81, 66, 0.12);
  font-size: 26rpx;
  font-weight: 800;
}
</style>
