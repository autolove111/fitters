<template>
  <view class="container">
    <!-- 综合健康指数卡片 -->
    <view class="score-card">
      <view class="score-left">
        <text class="score-label">今日健康指数</text>
        <text class="score-number">{{ dailyReport.score }}</text>
        <text class="score-unit">分</text>
      </view>
      <view class="score-ring">
        <view class="ring-bg"></view>
        <view class="ring-fill" :style="{ height: dailyReport.score + '%' }"></view>
        <text class="ring-text">{{ dailyReport.score }}%</text>
      </view>
    </view>

    <!-- 今日三项指标 -->
    <view class="stats-grid">
      <view class="stat-card">
        <view class="stat-header">
          <text class="stat-icon">🏃</text>
          <text class="stat-title">运动</text>
        </view>
        <text class="stat-value">{{ todayStats.workoutMinutes }} / {{ todayStats.workoutTarget }} 分钟</text>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: workoutPercent + '%', backgroundColor: '#409eff' }"></view>
        </view>
      </view>
      <view class="stat-card">
        <view class="stat-header">
          <text class="stat-icon">😴</text>
          <text class="stat-title">睡眠</text>
        </view>
        <text class="stat-value">{{ todayStats.sleepHours }} / {{ todayStats.sleepTarget }} 小时</text>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: sleepPercent + '%', backgroundColor: '#67c23a' }"></view>
        </view>
      </view>
      <view class="stat-card">
        <view class="stat-header">
          <text class="stat-icon">🍚</text>
          <text class="stat-title">饮食</text>
        </view>
        <text class="stat-value">{{ todayStats.dietCalories }} / {{ todayStats.dietTarget }} 千卡</text>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: dietPercent + '%', backgroundColor: '#e6a23c' }"></view>
        </view>
      </view>
    </view>

    <!-- 过去30天统计卡片 -->
    <view class="history-card">
      <view class="card-header">
        <text class="card-title">📊 过去30天统计</text>
        <text class="card-subtitle">基于历史数据</text>
      </view>
      <view class="history-stats-grid">
        <view class="history-stat-item">
          <text class="history-stat-label">总运动</text>
          <text class="history-stat-value">{{ historyStats.totalWorkout }}分钟</text>
        </view>
        <view class="history-stat-item">
          <text class="history-stat-label">日均运动</text>
          <text class="history-stat-value">{{ historyStats.avgWorkout }}分钟/天</text>
        </view>
        <view class="history-stat-item">
          <text class="history-stat-label">平均睡眠</text>
          <text class="history-stat-value">{{ historyStats.avgSleep }}小时/天</text>
        </view>
        <view class="history-stat-item">
          <text class="history-stat-label">日均摄入</text>
          <text class="history-stat-value">{{ historyStats.avgDiet }}千卡</text>
        </view>
        <view class="history-stat-item">
          <text class="history-stat-label">运动达标天数</text>
          <text class="history-stat-value">{{ historyStats.workoutGoalDays }}天</text>
        </view>
        <view class="history-stat-item">
          <text class="history-stat-label">睡眠达标天数</text>
          <text class="history-stat-value">{{ historyStats.sleepGoalDays }}天</text>
        </view>
      </view>
      <!-- 最近7天趋势简图 -->
      <view class="trend-section">
        <text class="trend-title">最近7天运动趋势</text>
        <view class="bars-container">
          <view v-for="(item, index) in weeklyTrend" :key="index" class="bar-item">
            <view class="bar" :style="{ height: item.height + 'px' }"></view>
            <text class="bar-label">{{ item.dayLabel }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 智能建议 -->
    <view class="advice-card">
      <text class="advice-icon">💡</text>
      <text class="advice-text">{{ advice }}</text>
    </view>

    <!-- 生成今日训练计划按钮+展示区 -->
    <view class="plan-section">
      <button class="generate-plan-btn" @click="generateTrainingPlan" :disabled="generatingPlan">
        <text v-if="!generatingPlan">🤖 生成今日训练计划</text>
        <text v-else>生成中...</text>
      </button>
      <view v-if="trainingPlan" class="plan-content">
        <text class="plan-title">📋 今日训练计划</text>
        <text class="plan-text">{{ trainingPlan }}</text>
      </view>
    </view>

    <!-- 快捷操作 -->
    <view class="action-buttons">
      <button class="action-btn primary" @click="navigateTo('workout/add')">➕ 运动</button>
      <button class="action-btn success" @click="navigateTo('sleep/add')">😴 睡眠</button>
      <button class="action-btn warning" @click="navigateTo('diet/add')">🍽️ 饮食</button>
    </view>

    <!-- 底部导航 -->
    <view class="bottom-nav">
      <button class="nav-btn" @click="navigateTo('history/index')">历史统计</button>
      <button class="nav-btn" @click="navigateTo('profile/index')">个人中心</button>
    </view>

    <!-- 加载遮罩 -->
    <view v-if="loading" class="loading-mask">
      <view class="loading-content">加载中...</view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/store/user'
import { statsApi } from '@/utils/api'

const userStore = useUserStore()
const { isLoggedIn } = userStore

// 界面状态
const loading = ref(false)
const generatingPlan = ref(false)
const trainingPlan = ref('')

// 今日数据
const todayStats = ref({
  workoutMinutes: 0,
  workoutTarget: 30,
  sleepHours: 0,
  sleepTarget: 8,
  dietCalories: 0,
  dietTarget: 2000
})
const dailyReport = ref({ score: 0 })
const advice = ref('')

// 历史统计相关
const historyStats = ref({
  totalWorkout: 0,
  avgWorkout: 0,
  avgSleep: 0,
  avgDiet: 0,
  workoutGoalDays: 0,
  sleepGoalDays: 0
})
const weeklyTrend = ref([]) // 最近7天趋势 { height, dayLabel }

// 百分比计算
const workoutPercent = computed(() => Math.min(100, (todayStats.value.workoutMinutes / todayStats.value.workoutTarget) * 100))
const sleepPercent = computed(() => Math.min(100, (todayStats.value.sleepHours / todayStats.value.sleepTarget) * 100))
const dietPercent = computed(() => {
  const consumed = todayStats.value.dietCalories
  const target = todayStats.value.dietTarget
  return consumed >= target ? 100 : (consumed / target) * 100
})

// ---------- 业务逻辑 ----------
async function loadDashboard() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    // 获取今日数据
    const today = await statsApi.today()
    todayStats.value = {
      workoutMinutes: today.workoutMinutes || 0,
      workoutTarget: today.workoutTarget || 30,
      sleepHours: today.sleepHours || 0,
      sleepTarget: today.sleepTarget || 8,
      dietCalories: today.dietCalories || 0,
      dietTarget: today.dietTarget || 2000
    }
    generateReportAndAdvice()

    // 获取过去30天历史数据
    await loadHistoryStats()
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function resetHistoryStatsToZero() {
  historyStats.value = {
    totalWorkout: 0,
    avgWorkout: 0,
    avgSleep: 0,
    avgDiet: 0,
    workoutGoalDays: 0,
    sleepGoalDays: 0
  }
  weeklyTrend.value = []  // 清空趋势图
}

async function loadHistoryStats() {
  try {
    const history = await statsApi.getHistory({ days: 30 })
    if (!history || history.length === 0) {
      resetHistoryStatsToZero()
      return
    }
    processHistoryData(history)
  } catch (error) {
    console.error('获取历史数据失败', error)
    resetHistoryStatsToZero()
  }
}

// 处理真实历史数据
function processHistoryData(history) {
  // 计算汇总
  const totalWorkout = history.reduce((sum, day) => sum + (day.workoutMinutes || 0), 0)
  const avgWorkout = Math.round(totalWorkout / history.length)
  const totalSleep = history.reduce((sum, day) => sum + (day.sleepHours || 0), 0)
  const avgSleep = (totalSleep / history.length).toFixed(1)
  const totalDiet = history.reduce((sum, day) => sum + (day.dietCalories || 0), 0)
  const avgDiet = Math.round(totalDiet / history.length)

  const workoutGoalDays = history.filter(day => (day.workoutMinutes || 0) >= (day.workoutTarget || 30)).length
  const sleepGoalDays = history.filter(day => (day.sleepHours || 0) >= (day.sleepTarget || 8)).length

  historyStats.value = {
    totalWorkout,
    avgWorkout,
    avgSleep,
    avgDiet,
    workoutGoalDays,
    sleepGoalDays
  }

  // 计算最近7天趋势（取最后7条，按日期升序）
  const last7 = history.slice(-7).reverse()
  const maxWorkout = Math.max(...last7.map(d => d.workoutMinutes || 0), 1)
  weeklyTrend.value = last7.map(day => {
    const minutes = day.workoutMinutes || 0
    const height = (minutes / maxWorkout) * 60
    // 格式化日期显示
    const date = new Date(day.date)
    const dayLabel = `${date.getMonth()+1}/${date.getDate()}`
    return { height: Math.max(4, height), dayLabel, minutes }
  })
}

// 生成当日报告和建议（基于今日数据）
function generateReportAndAdvice() {
  const w = todayStats.value.workoutMinutes
  const wTarget = todayStats.value.workoutTarget
  const s = todayStats.value.sleepHours
  const sTarget = todayStats.value.sleepTarget
  const d = todayStats.value.dietCalories
  const dTarget = todayStats.value.dietTarget

  const workoutScore = Math.min(100, (w / wTarget) * 100)
  const sleepScore = Math.min(100, (s / sTarget) * 100)
  const dietScore = Math.min(100, (dTarget - Math.abs(d - dTarget)) / dTarget * 100)
  const totalScore = Math.round((workoutScore + sleepScore + dietScore) / 3)
  dailyReport.value.score = totalScore

  let adviceText = ''
  if (s < 6) adviceText += '睡眠严重不足，建议今晚提前休息。'
  if (w > wTarget * 1.5 && s < 7) adviceText += '运动过量且睡眠不足，请降低强度。'
  if (d > dTarget) adviceText += '今日热量超标，下一餐宜清淡。'
  if (!adviceText) adviceText = '各项指标良好，继续保持！'
  advice.value = adviceText
}

// 调用 statsApi.generatePlan 生成训练计划
async function generateTrainingPlan() {
  if (generatingPlan.value) return
  generatingPlan.value = true
  trainingPlan.value = ''

  try {
    // 准备要发送的数据（与大模型交互所需）
    const requestData = {
      todayStats: {
        workoutMinutes: todayStats.value.workoutMinutes,
        workoutTarget: todayStats.value.workoutTarget,
        sleepHours: todayStats.value.sleepHours,
        sleepTarget: todayStats.value.sleepTarget,
        dietCalories: todayStats.value.dietCalories,
        dietTarget: todayStats.value.dietTarget,
        healthScore: dailyReport.value.score
      },
      historyStats: {
        avgWorkout: historyStats.value.avgWorkout,
        avgSleep: historyStats.value.avgSleep,
        avgDiet: historyStats.value.avgDiet,
        workoutGoalDays: historyStats.value.workoutGoalDays,
        sleepGoalDays: historyStats.value.sleepGoalDays
      },
      advice: advice.value
    }

    // 调用后端大模型代理接口
    const res = await statsApi.generatePlan(requestData)
    // 后端返回格式 { plan: "生成的计划文本" }
    trainingPlan.value = res.plan || '计划生成成功，但未返回具体内容。'
  } catch (error) {
    console.error('调用后端接口失败', error)
    trainingPlan.value = `🏋️ 今日训练计划建议（本地生成）：
1. 热身5分钟
2. 力量训练20分钟（俯卧撑、深蹲）
3. 有氧运动15分钟
4. 拉伸放松5分钟
根据身体感受调整，保持健康！`
    uni.showToast({ title: '调用后端接口失败，使用本地计划', icon: 'none' })
  } finally {
    generatingPlan.value = false
  }
}

function navigateTo(page) {
  uni.navigateTo({ url: `/pages/${page}` })
}

onMounted(() => {
  if (!isLoggedIn.value) {
    uni.reLaunch({ url: '/pages/index/index' })
  } else {
    loadDashboard()
    if (uni && typeof uni.$on === 'function') {
      uni.$on('historyRefresh', loadDashboard)
    }
  }
})
</script>

<style scoped>
.container {
  padding: 30rpx;
  background-color: #f5f7fa;
  min-height: 100vh;
  padding-bottom: 100rpx;
}

/* 健康指数卡片 */
.score-card {
  background: linear-gradient(135deg, #409eff 0%, #2c6ed1 100%);
  border-radius: 32rpx;
  padding: 40rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: white;
  margin-bottom: 30rpx;
}
.score-left {
  flex: 1;
}
.score-label {
  font-size: 28rpx;
  opacity: 0.9;
}
.score-number {
  font-size: 80rpx;
  font-weight: bold;
  line-height: 1.2;
  margin-right: 10rpx;
}
.score-unit {
  font-size: 32rpx;
}
.score-ring {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background-color: rgba(255,255,255,0.3);
  position: relative;
  overflow: hidden;
}
.ring-bg {
  width: 100%;
  height: 100%;
  background-color: rgba(255,255,255,0.2);
}
.ring-fill {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  background-color: white;
  transition: height 0.3s;
}
.ring-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 32rpx;
  font-weight: bold;
  color: #409eff;
}

/* 指标卡片 */
.stats-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
  margin-bottom: 30rpx;
}
.stat-card {
  flex: 1;
  min-width: 200rpx;
  background: white;
  border-radius: 24rpx;
  padding: 24rpx;
  box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.05);
}
.stat-header {
  display: flex;
  align-items: center;
  margin-bottom: 16rpx;
}
.stat-icon {
  font-size: 40rpx;
  margin-right: 10rpx;
}
.stat-title {
  font-size: 28rpx;
  color: #606266;
}
.stat-value {
  font-size: 28rpx;
  color: #303133;
  margin-bottom: 20rpx;
  display: block;
}
.progress-bar {
  background-color: #e0e0e0;
  border-radius: 8rpx;
  height: 8rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  width: 0%;
  transition: width 0.3s;
}

/* 历史卡片 */
.history-card {
  background: white;
  border-radius: 24rpx;
  padding: 30rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.05);
}
.card-header {
  margin-bottom: 20rpx;
}
.card-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #303133;
}
.card-subtitle {
  font-size: 24rpx;
  color: #909399;
  margin-left: 10rpx;
}
.history-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20rpx;
  margin-bottom: 30rpx;
}
.history-stat-item {
  background: #f5f7fa;
  padding: 16rpx;
  border-radius: 16rpx;
  text-align: center;
}
.history-stat-label {
  font-size: 24rpx;
  color: #606266;
  display: block;
  margin-bottom: 8rpx;
}
.history-stat-value {
  font-size: 32rpx;
  font-weight: bold;
  color: #303133;
}
.trend-section {
  margin-top: 20rpx;
}
.trend-title {
  font-size: 26rpx;
  color: #606266;
  display: block;
  margin-bottom: 16rpx;
}
.bars-container {
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  height: 120rpx;
}
.bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}
.bar {
  width: 30rpx;
  background: linear-gradient(135deg, #409eff, #2c6ed1);
  border-radius: 8rpx 8rpx 0 0;
  transition: height 0.3s ease;
  min-height: 4rpx;
}
.bar-label {
  font-size: 20rpx;
  color: #909399;
  margin-top: 8rpx;
}

/* 建议卡片 */
.advice-card {
  background: #ecf5ff;
  border-radius: 24rpx;
  padding: 24rpx;
  display: flex;
  align-items: center;
  margin-bottom: 30rpx;
}
.advice-icon {
  font-size: 40rpx;
  margin-right: 20rpx;
}
.advice-text {
  flex: 1;
  font-size: 28rpx;
  color: #2c3e50;
  line-height: 1.4;
}

/* 训练计划区域 */
.plan-section {
  margin-bottom: 30rpx;
}
.generate-plan-btn {
  background: linear-gradient(135deg, #67c23a, #529b2e);
  color: white;
  border: none;
  border-radius: 48rpx;
  height: 88rpx;
  line-height: 88rpx;
  font-size: 32rpx;
  margin-bottom: 20rpx;
}
.generate-plan-btn[disabled] {
  opacity: 0.6;
}
.plan-content {
  background: #f0f9ff;
  border-radius: 24rpx;
  padding: 30rpx;
  border-left: 8rpx solid #409eff;
}
.plan-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #303133;
  display: block;
  margin-bottom: 16rpx;
}
.plan-text {
  font-size: 28rpx;
  color: #606266;
  line-height: 1.6;
  white-space: pre-line;
}

/* 快捷按钮 */
.action-buttons {
  display: flex;
  gap: 20rpx;
  margin-bottom: 30rpx;
}
.action-btn {
  flex: 1;
  height: 88rpx;
  line-height: 88rpx;
  border-radius: 48rpx;
  font-size: 32rpx;
  border: none;
  color: white;
}
.action-btn.primary {
  background: linear-gradient(135deg, #409eff, #2c6ed1);
}
.action-btn.success {
  background-color: #67c23a;
}
.action-btn.warning {
  background-color: #e6a23c;
}

/* 底部导航 */
.bottom-nav {
  display: flex;
  gap: 20rpx;
}
.nav-btn {
  flex: 1;
  background-color: #f0f2f5;
  color: #606266;
  border: 1px solid #dcdfe6;
  border-radius: 48rpx;
  height: 70rpx;
  line-height: 70rpx;
  font-size: 28rpx;
}

/* 加载遮罩 */
.loading-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}
.loading-content {
  background: white;
  padding: 30rpx 60rpx;
  border-radius: 16rpx;
  font-size: 28rpx;
}
</style>