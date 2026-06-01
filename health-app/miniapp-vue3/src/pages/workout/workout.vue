<template>
  <view class="container" :class="{ dark: isDark }">
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
      <view class="stat-card" @click="openHistory('workout')">
        <view class="stat-header">
          <text class="stat-icon">🏃</text>
          <text class="stat-title">今日运动</text>
        </view>
        <text class="stat-value">{{ todayStats.workoutMinutes }} / {{ todayStats.workoutTarget }} 分钟</text>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: workoutPercent + '%', backgroundColor: '#409eff' }"></view>
        </view>
      </view>
      <view class="stat-card" @click="openHistory('sleep')">
        <view class="stat-header">
          <text class="stat-icon">😴</text>
          <text class="stat-title">今日睡眠</text>
        </view>
        <text class="stat-value">{{ todayStats.sleepHours }} / {{ todayStats.sleepTarget }} 小时</text>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: sleepPercent + '%', backgroundColor: '#67c23a' }"></view>
        </view>
      </view>
      <view class="stat-card" @click="openHistory('diet')">
        <view class="stat-header">
          <text class="stat-icon">🍚</text>
          <text class="stat-title">今日饮食</text>
        </view>
        <text class="stat-value">{{ todayStats.dietCalories }} / {{ todayStats.dietTarget }} 千卡</text>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: dietPercent + '%', backgroundColor: '#e6a23c' }"></view>
        </view>
      </view>
      <view class="stat-card" @click="openHistory('steps')">
        <view class="stat-header">
          <text class="stat-icon">👟</text>
          <text class="stat-title">今日步数</text>
        </view>
        <text class="stat-value">{{ todayStats.stepsCount }} / {{ todayStats.stepsTarget }} 步</text>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: stepsPercent + '%', backgroundColor: '#f56c6c' }"></view>
        </view>
      </view>
    </view>

    <!-- 智能建议 -->
    <!-- <view class="advice-card">
      <text class="advice-icon">💡</text>
      <text class="advice-text">{{ advice }}</text>
    </view> -->

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

    <!-- 加载遮罩 -->
    <view v-if="loading" class="loading-mask">
      <view class="loading-content">加载中...</view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/store/user'
import { useThemeStore } from '@/store/theme'
import { statsApi } from '@/utils/api'

const themeStore = useThemeStore()
const { isDark } = themeStore

const userStore = useUserStore()
const { isLoggedIn } = userStore

// 界面状态
const loading = ref(false)
const generatingPlan = ref(false)
const trainingPlan = ref('')

// 今日数据（将从后端接口填充）
const todayStats = ref({
  workoutMinutes: 0,
  workoutTarget: 30,
  sleepHours: 0,
  sleepTarget: 8,
  dietCalories: 0,
  dietTarget: 2000,
  stepsCount: 0,
  stepsTarget: 10000
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
  sleepGoalDays: 0,
  totalSteps: 0,
  avgSteps: 0
})
const weeklyTrend = ref([])

// 百分比计算
const workoutPercent = computed(() => Math.min(100, (todayStats.value.workoutMinutes / todayStats.value.workoutTarget) * 100))
const sleepPercent = computed(() => Math.min(100, (todayStats.value.sleepHours / todayStats.value.sleepTarget) * 100))
const dietPercent = computed(() => Math.min(100, (todayStats.value.dietCalories / todayStats.value.dietTarget) * 100))
const stepsPercent = computed(() => Math.min(100, (todayStats.value.stepsCount / todayStats.value.stepsTarget) * 100))

// 统计数据列表（用于历史卡片）
const statsList = computed(() => [
  { 
    label: '总运动', 
    value: `${historyStats.value.totalWorkout}分钟`, 
    info: '过去30天内所有运动时长的总和，单位：分钟。帮助您了解整体运动量。' 
  },
  { 
    label: '日均运动', 
    value: `${historyStats.value.avgWorkout}分钟/天`, 
    info: '过去30天平均每天的运动时长，反映您的日常运动习惯。' 
  },
  { 
    label: '平均睡眠', 
    value: `${historyStats.value.avgSleep}小时/天`, 
    info: '过去30天平均每天的睡眠时长，单位：小时。有助于评估睡眠规律性。' 
  },
  { 
    label: '日均摄入', 
    value: `${historyStats.value.avgDiet}千卡`, 
    info: '过去30天平均每天从饮食中摄入的热量，单位：千卡。用于监控能量平衡。' 
  },
  { 
    label: '总步数', 
    value: `${historyStats.value.totalSteps || 0}步`, 
    info: '过去30天内所有步数的总和。帮助您了解每日活动量。' 
  },
  { 
    label: '日均步数', 
    value: `${historyStats.value.avgSteps || 0}步`, 
    info: '过去30天平均每天的步数。用于判断日常步行水平。' 
  },
  { 
    label: '运动达标天数', 
    value: `${historyStats.value.workoutGoalDays}天`, 
    info: '过去30天中，运动时长达到或超过目标（默认30分钟）的天数。反映运动计划的执行情况。' 
  },
  { 
    label: '睡眠达标天数', 
    value: `${historyStats.value.sleepGoalDays}天`, 
    info: '过去30天中，睡眠时长达到或超过目标（默认8小时）的天数。帮助评估睡眠充足程度。' 
  }
])

// 为统计项添加图标映射
const getStatIcon = (label) => {
  const iconMap = {
    '总运动': '🏃‍♂️',
    '日均运动': '📈',
    '平均睡眠': '😴',
    '日均摄入': '🍽️',
    '总步数': '👟',
    '日均步数': '🚶',
    '运动达标天数': '🎯',
    '睡眠达标天数': '⭐'
  }
  return iconMap[label] || '📊'
}

// 显示统计项说明
const showStatInfo = (infoText) => {
  uni.showModal({
    title: '数据说明',
    content: infoText,
    showCancel: false,
    confirmText: '知道了'
  })
}

// ---------- 数据加载 ----------
async function loadDashboard() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    // 并行请求今日运动、睡眠、饮食数据
    const [todayData, sleepTodayData, dietTodayData] = await Promise.all([
      statsApi.today(),
      statsApi.sleepToday(),
      statsApi.dietToday()
    ])

    // 1. 运动数据
    const workoutTarget = todayData.targetMinutes ?? 30
    const workoutMinutes = todayData.completedMinutes ?? 0
    // 2. 睡眠数据
    const sleepTarget = sleepTodayData.targetHours ?? 8
    // 计算总睡眠时长（多条记录累加 durationHours）
    let sleepHours = 0
    if (sleepTodayData.records && Array.isArray(sleepTodayData.records)) {
      sleepHours = sleepTodayData.records.reduce((sum, r) => sum + (r.durationHours || 0), 0)
    }
    // 3. 饮食数据
    const dietTarget = dietTodayData.targetCalories ?? 2000
    const dietCalories = dietTodayData.totalCalories ?? 0
    const stepsTarget = todayData.stepsTarget ?? 10000
    const stepsCount = todayData.steps ?? 0

    todayStats.value = {
      workoutMinutes,
      workoutTarget,
      sleepHours,
      sleepTarget,
      dietCalories,
      dietTarget,
      stepsCount,
      stepsTarget
    }

    // 计算今日健康指数（基于完成百分比）
    const safeDivide = (a, b) => (b && b > 0 ? (a / b) * 100 : 0)
    const workoutScore = Math.min(100, safeDivide(workoutMinutes, workoutTarget))
    const sleepScore = Math.min(100, safeDivide(sleepHours, sleepTarget))
    // 饮食得分：越接近目标越高，使用偏差率计算（100 - 偏差百分比）
    const dietDiffPercent = dietTarget > 0 ? Math.abs(dietCalories - dietTarget) / dietTarget * 100 : 100
    const dietScore = Math.max(0, 100 - dietDiffPercent)
    const stepsScore = Math.min(100, safeDivide(stepsCount, stepsTarget))
    const totalScore = Math.round((workoutScore + sleepScore + dietScore + stepsScore) / 4)
    dailyReport.value.score = isNaN(totalScore) ? 0 : totalScore

    // 生成建议
    generateReportAndAdvice()

    // 加载历史数据
    await loadHistoryStats()
  } catch (e) {
    console.error('加载仪表盘数据失败', e)
    uni.showToast({ title: e.message || '加载失败，请检查网络', icon: 'none' })
  } finally {
    loading.value = false
  }
}

// 生成智能健康建议
function generateReportAndAdvice() {
  const w = todayStats.value.workoutMinutes
  const wTarget = todayStats.value.workoutTarget
  const s = todayStats.value.sleepHours
  const sTarget = todayStats.value.sleepTarget
  const d = todayStats.value.dietCalories
  const dTarget = todayStats.value.dietTarget
  
  const adviceList = []
  
  // 1. 睡眠分析
  if (s === 0) {
    adviceList.push('⚠️ 今日无睡眠记录，睡眠对健康至关重要，请保证充足休息。')
  } else if (s < 6) {
    adviceList.push('😴 睡眠严重不足（<6小时），长期缺觉会影响免疫力和记忆力，建议今晚提前1小时入睡。')
  } else if (s < 7) {
    adviceList.push('😌 睡眠偏少（6-7小时），建议适当增加睡眠时间，理想目标是8小时。')
  } else if (s >= 9) {
    adviceList.push('🛌 睡眠时间过长（>9小时），可能影响精力，建议保持规律作息。')
  } else if (s >= sTarget - 0.5 && s <= sTarget + 0.5) {
    adviceList.push('🎯 睡眠时长理想，继续保持！')
  }
  
  // 2. 运动分析
  if (w === 0) {
    adviceList.push('🏃 今日未运动，建议进行30分钟中等强度活动，如快走、慢跑。')
  } else if (w < wTarget * 0.5) {
    adviceList.push('📉 运动量不足，未达到目标的一半，建议增加运动频率或时长。')
  } else if (w < wTarget) {
    adviceList.push('💪 运动量接近目标，再坚持一下就能达标！')
  } else if (w >= wTarget && w < wTarget * 1.2) {
    adviceList.push('✅ 运动达标！继续保持这个好习惯。')
  } else if (w >= wTarget * 1.5) {
    adviceList.push('🏋️ 运动量较大，注意适当休息，避免过度训练导致受伤。')
  }
  
  // 3. 饮食分析
  const dietRatio = d / dTarget
  if (d === 0) {
    adviceList.push('🍽️ 今日无饮食记录，合理饮食是健康的基础，请记录三餐。')
  } else if (dietRatio < 0.6) {
    adviceList.push('⚠️ 热量摄入严重不足（低于目标60%），可能导致营养不良。')
  } else if (dietRatio < 0.9) {
    adviceList.push('🥗 热量摄入略低，可适当增加健康食物，确保能量充足。')
  } else if (dietRatio >= 1.1 && dietRatio <= 1.3) {
    adviceList.push('🍚 热量摄入略高，建议下一餐选择清淡食物。')
  } else if (dietRatio > 1.3) {
    adviceList.push('🔥 热量摄入超标较多，建议增加运动消耗，控制高热量食物。')
  } else if (dietRatio >= 0.95 && dietRatio <= 1.05) {
    adviceList.push('🎯 热量摄入精准达标，饮食控制得很好！')
  }
  
  // 4. 综合交叉分析
  if (w > wTarget * 1.2 && s < 7) {
    adviceList.push('⚠️ 运动量大但睡眠不足，身体恢复会受影响，今晚请早睡。')
  }
  
  if (s < 7 && d > dTarget) {
    adviceList.push('⚠️ 睡眠不足加上热量超标，容易导致体重增加，建议调整作息和饮食。')
  }
  
  if (w < wTarget * 0.5 && d > dTarget) {
    adviceList.push('⚠️ 运动不足且热量超标，体重管理面临挑战，建议增加运动。')
  }
  
  if (s >= 8 && w >= wTarget && dietRatio >= 0.9 && dietRatio <= 1.1) {
    adviceList.unshift('🌟 三项指标全部达标！今日表现完美，继续保持！')
  }
  
  // 5. 鼓励性建议
  if (adviceList.length === 0) {
    adviceList.push('👍 各项指标良好，继续保持健康生活方式！')
  }
  
  // 合并建议，用换行分隔
  advice.value = adviceList.join('\n')
}

// 加载历史统计数据
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

function resetHistoryStatsToZero() {
  historyStats.value = {
    totalWorkout: 0,
    avgWorkout: 0,
    avgSleep: 0,
    avgDiet: 0,
    workoutGoalDays: 0,
    sleepGoalDays: 0
  }
  weeklyTrend.value = []
}

function processHistoryData(history) {
  // 计算汇总
  const totalWorkout = history.reduce((sum, day) => sum + (day.workoutMinutes || 0), 0)
  const avgWorkout = Math.round(totalWorkout / history.length)
  const totalSleep = history.reduce((sum, day) => sum + (day.sleepHours || 0), 0)
  const avgSleep = (totalSleep / history.length).toFixed(1)
  const totalDiet = history.reduce((sum, day) => sum + (day.dietCalories || 0), 0)
  const avgDiet = Math.round(totalDiet / history.length)
  const totalSteps = history.reduce((sum, day) => sum + (day.steps || day.stepsCount || 0), 0)
  const avgSteps = history.length ? Math.round(totalSteps / history.length) : 0

  // 使用历史数据中的目标值（后端返回的 workoutTarget / sleepTarget / dietTarget）
  const workoutTarget = history[0]?.workoutTarget ?? 30
  const sleepTarget = history[0]?.sleepTarget ?? 8
  const workoutGoalDays = history.filter(day => (day.workoutMinutes || 0) >= workoutTarget).length
  const sleepGoalDays = history.filter(day => (day.sleepHours || 0) >= sleepTarget).length

  historyStats.value = {
    totalWorkout,
    avgWorkout,
    avgSleep,
    avgDiet,
    workoutGoalDays,
    sleepGoalDays,
    totalSteps,
    avgSteps
  }

  // 计算最近7天运动趋势
  const last7 = history.slice(-7).reverse()
  const maxWorkout = Math.max(...last7.map(d => d.workoutMinutes || 0), 1)
  weeklyTrend.value = last7.map(day => {
    const minutes = day.workoutMinutes || 0
    const height = (minutes / maxWorkout) * 60
    const date = new Date(day.date)
    const dayLabel = `${date.getMonth()+1}/${date.getDate()}`
    return { height: Math.max(4, height), dayLabel, minutes }
  })
}

// 生成训练计划（依赖今日数据和历史数据）
async function generateTrainingPlan() {
  if (generatingPlan.value) return
  generatingPlan.value = true
  trainingPlan.value = ''

  try {
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
    const res = await statsApi.generatePlan(requestData)
    const lines = []
    if (res.summary) lines.push(res.summary)
    if (Array.isArray(res.items) && res.items.length) {
      lines.push('')
      res.items.forEach((item, index) => {
        lines.push(`${index + 1}. ${item.stage}：${item.activity} ${item.minutes}分钟（${item.intensity}）`)
        if (item.notes) lines.push(`   ${item.notes}`)
      })
    }
    if (Array.isArray(res.tips) && res.tips.length) {
      lines.push('', '小提示：')
      res.tips.forEach((tip, index) => {
        lines.push(`${index + 1}. ${tip}`)
      })
    }
    trainingPlan.value = lines.join('\n') || '今日训练计划已生成，但暂无可展示内容。'
  } catch (error) {
    console.error('调用后端接口失败', error)
    trainingPlan.value = ''
    uni.showToast({ title: error.message || '生成计划失败', icon: 'none' })
  } finally {
    generatingPlan.value = false
  }
}

function openHistory(metric) {
  uni.navigateTo({ url: `/pages/workout/history?metric=${metric}` })
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
  background-color: var(--bg-primary);
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
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20rpx;
  margin-bottom: 30rpx;
}
.stat-card {
  flex: 1;
  min-width: 200rpx;
  background: var(--card-bg);
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
  color: var(--text-secondary);
}
.stat-value {
  font-size: 28rpx;
  color: var(--text-primary);
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

/* 过去30天统计相关样式已删除 */

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
  color: var(--text-primary);
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
  color: var(--text-primary);
  display: block;
  margin-bottom: 16rpx;
}
.plan-text {
  font-size: 28rpx;
  color: var(--text-secondary);
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
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}
.loading-content {
  background: var(--modal-bg);
  padding: 30rpx 60rpx;
  border-radius: 16rpx;
  font-size: 28rpx;
}
</style>
