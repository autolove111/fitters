<template>
  <scroll-view class="report-container" scroll-y>
    <view class="report-inner">
      <view class="report-header">
        <text class="title">月度养生报告</text>
        <text class="subtitle">{{ currentYearMonth }}</text>
      </view>

      <!-- 核心指标卡片 -->
      <view class="stats-card">
        <view class="stat-item">
          <text class="stat-value">{{ totalCheckinDays }}</text>
          <text class="stat-label">本月打卡天数</text>
        </view>
        <view class="stat-divider"></view>
        <view class="stat-item">
          <text class="stat-value">{{ completionRate }}%</text>
          <text class="stat-label">任务完成率</text>
        </view>
        <view class="stat-divider"></view>
        <view class="stat-item">
          <text class="stat-value">{{ bestTask }}</text>
          <text class="stat-label">最坚持任务</text>
        </view>
      </view>

      <!-- 任务完成排行 -->
      <view class="rank-card">
        <view class="card-header">
          <text class="card-icon">🏅</text>
          <text class="card-title">任务完成排行</text>
        </view>
        <view class="rank-list">
          <view v-for="item in taskRanking" :key="item.name" class="rank-item">
            <text class="rank-name">{{ item.name }}</text>
            <view class="rank-bar-bg">
              <view class="rank-bar" :style="{ width: item.percent + '%' }"></view>
            </view>
            <text class="rank-count">{{ item.count }}次</text>
          </view>
        </view>
      </view>

      <!-- 最佳连续打卡 & 健康评分 -->
      <view class="two-columns">
        <view class="half-card">
          <text class="half-icon">🔥</text>
          <text class="half-title">最佳连续打卡</text>
          <text class="big-number">{{ bestStreak }}</text>
          <text class="unit">天</text>
        </view>
        <view class="half-card">
          <text class="half-icon">💚</text>
          <text class="half-title">健康评分</text>
          <text class="big-number">{{ healthScore }}</text>
          <text class="unit">分</text>
          <text class="score-level" :class="scoreLevelClass">{{ healthLevel }}</text>
        </view>
      </view>

      <!-- 打卡时段分布 -->
      <view class="period-card">
        <view class="card-header">
          <text class="card-icon">📆</text>
          <text class="card-title">打卡时段分布</text>
        </view>
        <view class="period-stats">
          <view class="period-item">
            <text class="period-icon">🌅</text>
            <text class="period-label">上半月 (1-15日)</text>
            <text class="period-value">{{ firstHalfDays }} 天</text>
          </view>
          <view class="period-item">
            <text class="period-icon">🌙</text>
            <text class="period-label">下半月 (16-月底)</text>
            <text class="period-value">{{ secondHalfDays }} 天</text>
          </view>
        </view>
        <view class="period-advice">
          <text class="tip-icon">📌</text>
          <text class="tip-text">{{ periodAdvice }}</text>
        </view>
      </view>

      <!-- 健康改善趋势 -->
      <view class="trend-card">
        <view class="card-header">
          <text class="card-icon">📈</text>
          <text class="card-title">健康改善趋势</text>
        </view>
        <text class="trend-text">{{ trendText }}</text>
        <view class="trend-tip">
          <text class="tip-icon">💡</text>
          <text class="tip-text">{{ adviceText }}</text>
        </view>
      </view>

      <button class="back-btn" @click="goBack">返回养生主页</button>
    </view>
  </scroll-view>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useUserStore } from '@/store/user'
import { wellnessApi } from '@/utils/api'

const userStore = useUserStore()
const username = userStore.state.username || 'guest'

const currentYearMonth = ref('')
const totalCheckinDays = ref(0)
const completionRate = ref(0)
const bestTask = ref('')
const trendText = ref('')
const adviceText = ref('')
const taskRanking = ref([])
const bestStreak = ref(0)
const healthScore = ref(0)
const healthLevel = ref('')
const firstHalfDays = ref(0)
const secondHalfDays = ref(0)
const periodAdvice = ref('')

const scoreLevelClass = computed(() => {
  if (healthScore.value >= 90) return 'level-excellent'
  if (healthScore.value >= 70) return 'level-good'
  if (healthScore.value >= 50) return 'level-pass'
  return 'level-need'
})

// 从本地存储读取数据（后备）
function loadFromLocalStorage(year, month) {
  const key = `checkin_${username}`
  const data = uni.getStorageSync(key) || {}
  const daysInMonth = new Date(year, month, 0).getDate()
  let checkinDays = 0
  let taskCount = { water: 0, footbath: 0, earlySleep: 0, walk: 0 }
  let totalTasksCompleted = 0
  let currentStreak = 0
  let maxStreak = 0
  let previousDayWasCheckin = false
  let firstHalf = 0
  let secondHalf = 0

  for (let day = 1; day <= daysInMonth; day++) {
    const dayStr = `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`
    const dayData = data[dayStr]
    const tasks = dayData ? dayData.tasks : {}
    const hasCheckin = tasks && Object.values(tasks).some(v => v === true)
    if (hasCheckin) {
      checkinDays++
      if (day <= 15) firstHalf++
      else secondHalf++
      if (previousDayWasCheckin) {
        currentStreak++
      } else {
        currentStreak = 1
      }
      if (currentStreak > maxStreak) maxStreak = currentStreak
      previousDayWasCheckin = true
      for (const taskId of Object.keys(taskCount)) {
        if (tasks[taskId]) taskCount[taskId]++
      }
      totalTasksCompleted += Object.values(tasks).filter(v => v === true).length
    } else {
      previousDayWasCheckin = false
      currentStreak = 0
    }
  }

  totalCheckinDays.value = checkinDays
  bestStreak.value = maxStreak
  firstHalfDays.value = firstHalf
  secondHalfDays.value = secondHalf
  const totalPossibleTasks = daysInMonth * Object.keys(taskCount).length
  const completion = totalPossibleTasks === 0 ? 0 : (totalTasksCompleted / totalPossibleTasks) * 100
  completionRate.value = Math.round(completion)
  const daysScore = (checkinDays / daysInMonth) * 60
  const taskScore = (completion / 100) * 40
  let score = Math.round(daysScore + taskScore)
  healthScore.value = score
  if (score >= 90) healthLevel.value = '优秀'
  else if (score >= 70) healthLevel.value = '良好'
  else if (score >= 50) healthLevel.value = '及格'
  else healthLevel.value = '需努力'

  const taskNames = { water: '喝水', footbath: '泡脚', earlySleep: '早睡', walk: '散步' }
  const ranking = []
  for (const [id, count] of Object.entries(taskCount)) {
    const percent = checkinDays === 0 ? 0 : (count / checkinDays) * 100
    ranking.push({ name: taskNames[id], count, percent: Math.round(percent) })
  }
  ranking.sort((a, b) => b.count - a.count)
  taskRanking.value = ranking
  bestTask.value = ranking[0]?.name || '无'

  if (firstHalf > secondHalf + 3) {
    periodAdvice.value = '上半月打卡更积极，下半月略有松懈。建议设置下半月提醒，保持均衡。'
  } else if (secondHalf > firstHalf + 3) {
    periodAdvice.value = '下半月打卡明显提升，后劲十足！继续保持。'
  } else {
    periodAdvice.value = '打卡分布较均衡，习惯养成得很好。'
  }

  if (score >= 80) {
    trendText.value = '🎉 非常优秀！您几乎每天都在坚持养生打卡，健康状态持续向好。'
    adviceText.value = '继续保持，可以尝试增加新的养生习惯，如冥想或拉伸。'
  } else if (score >= 60) {
    trendText.value = '👍 不错哦，超过一半的时间在坚持，健康改善明显。'
    adviceText.value = '建议固定每天打卡时间，形成生物钟。'
  } else if (score >= 40) {
    trendText.value = '🌱 有进步，但还需要更多坚持，健康提升需要日积月累。'
    adviceText.value = '可以从“喝水”和“散步”这种简单任务开始，逐步增加。'
  } else {
    trendText.value = '🍃 本月打卡较少，下周开始尝试每天完成一个小任务吧！'
    adviceText.value = '设定手机提醒，加入养生社群互相激励。'
  }
}

async function loadMonthlyReport() {
  const now = new Date()
  const currentYear = now.getFullYear()
  const currentMonth = now.getMonth() + 1
  currentYearMonth.value = `${currentYear}年${currentMonth}月`
  const yearMonth = `${currentYear}-${String(currentMonth).padStart(2,'0')}`

  try {
    const res = await wellnessApi.getMonthlyCheckin(yearMonth)
    const checkins = res.checkins || []
    const daysInMonth = new Date(currentYear, currentMonth, 0).getDate()
    let checkinDays = 0
    let taskCount = { water: 0, footbath: 0, earlySleep: 0, walk: 0 }
    let totalTasksCompleted = 0
    let currentStreak = 0
    let maxStreak = 0
    let previousDayWasCheckin = false
    let firstHalf = 0
    let secondHalf = 0
    const checkinMap = {}
    checkins.forEach(item => {
      checkinMap[item.date] = item.tasks
    })
    for (let day = 1; day <= daysInMonth; day++) {
      const dayStr = `${currentYear}-${String(currentMonth).padStart(2,'0')}-${String(day).padStart(2,'0')}`
      const tasks = checkinMap[dayStr] || {}
      const hasCheckin = Object.values(tasks).some(v => v === true)
      if (hasCheckin) {
        checkinDays++
        if (day <= 15) firstHalf++
        else secondHalf++
        if (previousDayWasCheckin) {
          currentStreak++
        } else {
          currentStreak = 1
        }
        if (currentStreak > maxStreak) maxStreak = currentStreak
        previousDayWasCheckin = true
        for (const taskId of Object.keys(taskCount)) {
          if (tasks[taskId]) taskCount[taskId]++
        }
        totalTasksCompleted += Object.values(tasks).filter(v => v === true).length
      } else {
        previousDayWasCheckin = false
        currentStreak = 0
      }
    }
    totalCheckinDays.value = checkinDays
    bestStreak.value = maxStreak
    firstHalfDays.value = firstHalf
    secondHalfDays.value = secondHalf
    const totalPossibleTasks = daysInMonth * Object.keys(taskCount).length
    const completion = (totalTasksCompleted / totalPossibleTasks) * 100
    completionRate.value = Math.round(completion)
    const daysScore = (checkinDays / daysInMonth) * 60
    const taskScore = (completion / 100) * 40
    let score = Math.round(daysScore + taskScore)
    healthScore.value = score
    if (score >= 90) healthLevel.value = '优秀'
    else if (score >= 70) healthLevel.value = '良好'
    else if (score >= 50) healthLevel.value = '及格'
    else healthLevel.value = '需努力'

    const taskNames = { water: '喝水', footbath: '泡脚', earlySleep: '早睡', walk: '散步' }
    const ranking = []
    for (const [id, count] of Object.entries(taskCount)) {
      const percent = checkinDays === 0 ? 0 : (count / checkinDays) * 100
      ranking.push({ name: taskNames[id], count, percent: Math.round(percent) })
    }
    ranking.sort((a, b) => b.count - a.count)
    taskRanking.value = ranking
    bestTask.value = ranking[0]?.name || '无'

    if (firstHalf > secondHalf + 3) {
      periodAdvice.value = '上半月打卡更积极，下半月略有松懈。建议设置下半月提醒，保持均衡。'
    } else if (secondHalf > firstHalf + 3) {
      periodAdvice.value = '下半月打卡明显提升，后劲十足！继续保持。'
    } else {
      periodAdvice.value = '打卡分布较均衡，习惯养成得很好。'
    }

    if (score >= 80) {
      trendText.value = '🎉 非常优秀！您几乎每天都在坚持养生打卡，健康状态持续向好。'
      adviceText.value = '继续保持，可以尝试增加新的养生习惯，如冥想或拉伸。'
    } else if (score >= 60) {
      trendText.value = '👍 不错哦，超过一半的时间在坚持，健康改善明显。'
      adviceText.value = '建议固定每天打卡时间，形成生物钟。'
    } else if (score >= 40) {
      trendText.value = '🌱 有进步，但还需要更多坚持，健康提升需要日积月累。'
      adviceText.value = '可以从“喝水”和“散步”这种简单任务开始，逐步增加。'
    } else {
      trendText.value = '🍃 本月打卡较少，下周开始尝试每天完成一个小任务吧！'
      adviceText.value = '设定手机提醒，加入养生社群互相激励。'
    }
  } catch (error) {
    console.error('后端加载失败，使用本地数据', error)
    uni.showToast({ title: '后端连接失败，使用本地数据', icon: 'none', duration: 2000 })
    loadFromLocalStorage(currentYear, currentMonth)
  }
}

function goBack() {
  uni.navigateBack()
}

onMounted(() => {
  loadMonthlyReport()
})
</script>

<style scoped>
/* 外层滚动容器 - 淡米色背景（与养生主页背景一致） */
.report-container {
  width: 100%;
  min-height: 100vh;
  overflow-x: hidden;
  background: linear-gradient(180deg, #f0f9f0 0%, #e8f5e9 100%);
  box-sizing: border-box;
}

.report-inner {
  padding: 30rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
  width: 100%;
}

.report-header {
  text-align: center;
  margin-bottom: 40rpx;
}
.title {
  font-size: 52rpx;
  font-weight: 800;
  background: linear-gradient(135deg, #2e7d32, #66bb6a);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  display: block;
  margin-bottom: 8rpx;
}
.subtitle {
  font-size: 28rpx;
  color: #558b2f;
  background: rgba(255,255,240,0.8);
  display: inline-block;
  padding: 8rpx 24rpx;
  border-radius: 60rpx;
}

/* 所有卡片统一使用淡绿渐变 */
.stats-card,
.rank-card,
.half-card,
.period-card,
.trend-card {
  background: linear-gradient(125deg, #e8f5e9, #c8e6c9);
  border-radius: 56rpx;
  box-shadow: 0 12rpx 28rpx rgba(0,0,0,0.06);
}

/* 核心指标卡片 */
.stats-card {
  padding: 40rpx 20rpx;
  display: flex;
  justify-content: space-around;
  align-items: center;
  margin-bottom: 30rpx;
}
.stat-item {
  text-align: center;
  flex: 1;
}
.stat-divider {
  width: 2rpx;
  height: 60rpx;
  background: rgba(70,100,50,0.2);
}
.stat-value {
  font-size: 48rpx;
  font-weight: 800;
  color: #2e7d32;
  display: block;
}
.stat-label {
  font-size: 26rpx;
  color: #5a7a4a;
  margin-top: 8rpx;
}

/* 通用卡片头部 */
.card-header {
  display: flex;
  align-items: center;
  margin-bottom: 24rpx;
}
.card-icon {
  font-size: 40rpx;
  margin-right: 12rpx;
}
.card-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #2e5a2a;
}

/* 任务排行卡片 */
.rank-card {
  padding: 30rpx;
  margin-bottom: 30rpx;
}
.rank-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.rank-item {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.rank-name {
  width: 80rpx;
  font-size: 28rpx;
  font-weight: 600;
  color: #3a6b2a;
}
.rank-bar-bg {
  flex: 1;
  height: 16rpx;
  background: rgba(100,140,80,0.25);
  border-radius: 16rpx;
  overflow: hidden;
}
.rank-bar {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #2e7d32);
  border-radius: 16rpx;
}
.rank-count {
  width: 80rpx;
  font-size: 26rpx;
  color: #5a7a3a;
  text-align: right;
}

/* 两列布局 */
.two-columns {
  display: flex;
  gap: 24rpx;
  margin-bottom: 30rpx;
}
.half-card {
  flex: 1;
  padding: 30rpx 20rpx;
  text-align: center;
}
.half-icon {
  font-size: 44rpx;
  display: block;
  margin-bottom: 12rpx;
}
.half-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #3a6b2a;
  display: block;
  margin-bottom: 16rpx;
}
.big-number {
  font-size: 64rpx;
  font-weight: 800;
  color: #c27e2a;
  display: inline-block;
  margin-right: 8rpx;
}
.unit {
  font-size: 28rpx;
  color: #6b8a4a;
}
.score-level {
  display: inline-block;
  font-size: 24rpx;
  padding: 6rpx 20rpx;
  border-radius: 40rpx;
  margin-top: 16rpx;
  background: rgba(200,230,180,0.7);
  color: #2e7d32;
}
/* 等级标签保留原色 */
.level-excellent { background: #a5d6a7; color: #1b5e20; }
.level-good { background: #c8e6c9; color: #2e7d32; }
.level-pass { background: #fff9c4; color: #b26a00; }
.level-need { background: #ffcdd2; color: #c62828; }

/* 时段分析卡片 */
.period-card {
  padding: 30rpx;
  margin-bottom: 30rpx;
}
.period-stats {
  display: flex;
  justify-content: space-around;
  margin: 20rpx 0 24rpx;
}
.period-item {
  text-align: center;
}
.period-icon {
  font-size: 36rpx;
  display: block;
  margin-bottom: 8rpx;
}
.period-label {
  font-size: 26rpx;
  color: #5a754a;
  display: block;
  margin-bottom: 8rpx;
}
.period-value {
  font-size: 40rpx;
  font-weight: 700;
  color: #2e7d32;
}
.period-advice {
  background: rgba(160,200,130,0.3);
  border-radius: 36rpx;
  padding: 16rpx 20rpx;
  display: flex;
  align-items: center;
  margin-top: 8rpx;
}

/* 趋势卡片 */
.trend-card {
  padding: 30rpx;
  margin-bottom: 30rpx;
}
.trend-text {
  font-size: 28rpx;
  line-height: 1.5;
  color: #3a5a2a;
  margin-bottom: 20rpx;
  padding: 0 8rpx;
}
.trend-tip {
  background: rgba(160,200,130,0.3);
  border-radius: 36rpx;
  padding: 16rpx 20rpx;
  display: flex;
  align-items: center;
}
.tip-icon {
  font-size: 36rpx;
  margin-right: 16rpx;
}
.tip-text {
  flex: 1;
  font-size: 26rpx;
  color: #5a7a3a;
  line-height: 1.4;
}

/* 返回按钮 */
.back-btn {
  background: linear-gradient(135deg, #43a047, #2e7d32);
  color: white;
  border-radius: 60rpx;
  height: 90rpx;
  line-height: 90rpx;
  font-size: 32rpx;
  font-weight: 600;
  border: none;
  width: 100%;
  box-sizing: border-box;
  margin-top: 20rpx;
  box-shadow: 0 8rpx 18rpx rgba(0,0,0,0.1);
}
.back-btn:active {
  transform: scale(0.98);
}
</style>