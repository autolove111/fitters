<template>
  <view class="weightloss-container">

    <scroll-view class="scroll-content" scroll-y :enhanced="true" :show-scrollbar="false">
      <!-- 核心数据卡片 -->
      <view class="stats-card">
        <view class="stats-header">
          <text class="stats-label">🎯 今日状态</text>
          <view class="goal-edit" @click="openGoalModal">
            <text class="edit-icon">✏️</text>
            <text class="edit-text">目标</text>
          </view>
        </view>

        <!-- 体重双圆环进度展示 -->
        <view class="weight-progress-area">
          <view class="weight-item current">
            <text class="weight-value">{{ currentWeight.toFixed(1) }}</text>
            <text class="weight-unit">kg</text>
            <text class="weight-label">当前体重</text>
          </view>
          <view class="progress-ring-wrapper">
            <view class="progress-ring">
              <view class="ring-bg"></view>
              <view class="ring-fill" :style="{ transform: `rotate(${progressAngle}deg)` }"></view>
              <view class="ring-inner">
                <text class="progress-percent">{{ progressPercent }}%</text>
                <text class="progress-text">完成度</text>
              </view>
            </view>
          </view>
          <view class="weight-item target">
            <text class="weight-value">{{ goalWeight.toFixed(1) }}</text>
            <text class="weight-unit">kg</text>
            <text class="weight-label">目标体重</text>
          </view>
        </view>

        <!-- 减重摘要 -->
        <view class="summary-row">
          <view class="summary-item">
            <text class="summary-number">{{ (startWeight - currentWeight).toFixed(1) }}</text>
            <text class="summary-desc">已减 kg</text>
          </view>
          <view class="summary-divider"></view>
          <view class="summary-item">
            <text class="summary-number">{{ (currentWeight - goalWeight).toFixed(1) }}</text>
            <text class="summary-desc">还需减 kg</text>
          </view>
          <view class="summary-divider"></view>
          <view class="summary-item">
            <text class="summary-number">{{ bmrCalories }}</text>
            <text class="summary-desc">基代 kcal</text>
          </view>
        </view>
      </view>

      <!-- 体重记录卡片 -->
      <view class="record-card">
        <view class="card-header">
          <text class="card-title">📊 体重记录</text>
          <view class="add-record-btn" @click="openRecordModal">
            <text class="add-icon">+</text>
            <text class="add-text">记录</text>
          </view>
        </view>

        <!-- 记录列表 -->
        <view v-if="weightRecords.length > 0" class="record-list">
          <view v-for="(record, index) in recentRecords" :key="index" class="record-item">
            <view class="record-date">
              <text class="date-day">{{ record.dateStr.split('-')[2] }}</text>
              <text class="date-month">{{ record.dateStr.slice(0,7) }}</text>
            </view>
            <view class="record-weight-info">
              <text class="record-weight">{{ record.weight.toFixed(1) }} kg</text>
              <text class="record-trend" :class="getTrendClass(record, index)">
                {{ getTrendText(record, index) }}
              </text>
            </view>
          </view>
        </view>
        <view v-else class="empty-records">
          <text class="empty-icon">📝</text>
          <text class="empty-text">暂无记录，点击右上角添加</text>
        </view>

        <!-- 轻量趋势提示 -->
        <view class="trend-tip" v-if="weightRecords.length >= 2">
          <text class="tip-icon">📉</text>
          <text class="tip-text">最近变化：{{ trendDescription }}</text>
        </view>
      </view>

      <!-- 饮食与运动推荐双栏 -->
      <view class="recommend-grid">
        <view class="rec-card diet-card">
          <view class="rec-header">
            <text class="rec-icon">🥗</text>
            <text class="rec-title">今日优选饮食</text>
          </view>
          <view class="food-list">
            <view class="food-item" v-for="food in dailyDiet" :key="food.name">
              <text class="food-name">{{ food.name }}</text>
              <text class="food-cal">{{ food.cal }} kcal</text>
            </view>
          </view>
          <view class="calorie-tip">
            <text>🔥 建议每日摄入 ≈ {{ recommendIntake }} kcal</text>
          </view>
        </view>

        <view class="rec-card exercise-card">
          <view class="rec-header">
            <text class="rec-icon">🏃‍♀️</text>
            <text class="rec-title">燃脂运动推荐</text>
          </view>
          <view class="exercise-list">
            <view class="exercise-item" v-for="exercise in dailyExercise" :key="exercise.name">
              <text class="exercise-name">{{ exercise.name }}</text>
              <text class="exercise-cal">🔥 {{ exercise.cal }} kcal/30min</text>
            </view>
          </view>
          <view class="encourage-text">
            <text>✨ 每天坚持30分钟，燃脂更高效</text>
          </view>
        </view>
      </view>

      <!-- 激励语录 -->
      <view class="motivation-card">
        <text class="quote-icon">💚</text>
        <text class="quote-text">{{ motivationQuote }}</text>
        <text class="quote-icon">🌿</text>
      </view>

      <view class="bottom-safe"></view>
    </scroll-view>

    <!-- 自定义弹窗：修改目标 -->
    <view v-if="showGoalModal" class="modal-mask" @click="showGoalModal = false">
      <view class="popup-container" @click.stop>
        <text class="popup-title">修改减重目标</text>
        <view class="popup-input-area">
          <text class="input-label">目标体重 (kg)</text>
          <input class="popup-input" type="digit" v-model="tempGoalWeight" placeholder="请输入目标体重" />
        </view>
        <view class="popup-buttons">
          <button class="popup-btn cancel" @click="showGoalModal = false">取消</button>
          <button class="popup-btn confirm" @click="updateGoalWeight">确定</button>
        </view>
      </view>
    </view>

    <!-- 自定义弹窗：添加体重记录 -->
    <view v-if="showRecordModal" class="modal-mask" @click="showRecordModal = false">
      <view class="popup-container" @click.stop>
        <text class="popup-title">记录今日体重</text>
        <view class="popup-input-area">
          <text class="input-label">体重 (kg)</text>
          <input class="popup-input" type="digit" v-model="tempWeight" placeholder="例如 65.5" />
        </view>
        <view class="popup-buttons">
          <button class="popup-btn cancel" @click="showRecordModal = false">取消</button>
          <button class="popup-btn confirm" @click="addWeightRecord">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()
const username = computed(() => userStore.state?.username || 'user')
const isLoggedIn = computed(() => userStore.isLoggedIn)

// ---------- 辅助函数 ----------
function formatDate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

// 存储key（基于用户名隔离）
function getStorageKey() {
  return `weightloss_${username.value}`
}

// ---------- 响应式数据 ----------
const goalWeight = ref(60)
const currentWeight = ref(70)
const weightRecords = ref([]) // { date, weight, dateStr }

// UI弹窗控制
const showGoalModal = ref(false)
const showRecordModal = ref(false)
const tempGoalWeight = ref('')
const tempWeight = ref('')

// ---------- 数据加载与保存 ----------
function loadData() {
  const key = getStorageKey()
  const stored = uni.getStorageSync(key)
  if (stored) {
    goalWeight.value = stored.goalWeight ?? 60
    weightRecords.value = stored.weightRecords ?? []
    if (weightRecords.value.length > 0) {
      const sorted = [...weightRecords.value].sort((a, b) => b.date - a.date)
      currentWeight.value = sorted[0].weight
    } else {
      currentWeight.value = 70
    }
  } else {
    // 初始化一条今日记录
    const today = new Date()
    const todayStr = formatDate(today)
    const defaultRecords = [{
      date: today.getTime(),
      weight: 70,
      dateStr: todayStr
    }]
    weightRecords.value = defaultRecords
    currentWeight.value = 70
    goalWeight.value = 60
    saveData()
  }
}

function saveData() {
  const key = getStorageKey()
  const data = {
    goalWeight: goalWeight.value,
    weightRecords: weightRecords.value
  }
  uni.setStorageSync(key, data)
}

// 更新当前体重（从最新记录同步）
function updateCurrentFromRecords() {
  if (weightRecords.value.length === 0) return
  const sorted = [...weightRecords.value].sort((a, b) => b.date - a.date)
  currentWeight.value = sorted[0].weight
}

// ---------- 计算属性 ----------
const startWeight = computed(() => {
  if (weightRecords.value.length === 0) return currentWeight.value
  const sorted = [...weightRecords.value].sort((a, b) => a.date - b.date)
  return sorted[0].weight
})

const progressPercent = computed(() => {
  const totalToLose = startWeight.value - goalWeight.value
  if (totalToLose <= 0) return 100
  const lostSoFar = startWeight.value - currentWeight.value
  let percent = (lostSoFar / totalToLose) * 100
  percent = Math.min(100, Math.max(0, percent))
  return Math.floor(percent)
})

const progressAngle = computed(() => {
  return (progressPercent.value / 100) * 360
})

const bmrCalories = computed(() => {
  return Math.floor(22 * currentWeight.value)
})

const recommendIntake = computed(() => {
  return Math.floor(bmrCalories.value * 1.2 - 300)
})

const recentRecords = computed(() => {
  return [...weightRecords.value].sort((a, b) => b.date - a.date).slice(0, 5)
})

const trendDescription = computed(() => {
  if (weightRecords.value.length < 2) return '暂无趋势'
  const sorted = [...weightRecords.value].sort((a, b) => a.date - b.date)
  const oldest = sorted[0].weight
  const latest = sorted[sorted.length - 1].weight
  const diff = latest - oldest
  if (diff < -0.3) return `近期已减 ${Math.abs(diff).toFixed(1)} kg，势头很好！`
  if (diff > 0.3) return `体重略有回升，注意饮食运动喔`
  return `保持稳定，继续加油`
})

// 获取单条记录对比样式/文本
function getTrendClass(record, idx) {
  const recordsSorted = [...weightRecords.value].sort((a, b) => b.date - a.date)
  if (idx === 0) return ''
  const prev = recordsSorted[idx - 1]
  if (!prev) return ''
  if (record.weight < prev.weight) return 'trend-down'
  if (record.weight > prev.weight) return 'trend-up'
  return 'trend-steady'
}
function getTrendText(record, idx) {
  const recordsSorted = [...weightRecords.value].sort((a, b) => b.date - a.date)
  if (idx === 0) return '最新'
  const prev = recordsSorted[idx - 1]
  if (!prev) return ''
  const diff = record.weight - prev.weight
  if (diff < -0.1) return `▼ ${Math.abs(diff).toFixed(1)}`
  if (diff > 0.1) return `▲ ${diff.toFixed(1)}`
  return '→ 持平'
}

// 动态饮食推荐
const dailyDiet = computed(() => {
  if (currentWeight.value > 80) {
    return [
      { name: '杂粮饭(150g)', cal: 180 },
      { name: '香煎鸡胸肉', cal: 200 },
      { name: '清炒西兰花', cal: 80 },
      { name: '无糖酸奶', cal: 90 }
    ]
  } else if (currentWeight.value > 65) {
    return [
      { name: '燕麦全麦吐司', cal: 150 },
      { name: '虾仁炒蛋', cal: 180 },
      { name: '蒜蓉空心菜', cal: 70 },
      { name: '苹果', cal: 85 }
    ]
  } else {
    return [
      { name: '藜麦沙拉', cal: 220 },
      { name: '清蒸鲈鱼', cal: 160 },
      { name: '菌菇汤', cal: 45 },
      { name: '蓝莓', cal: 60 }
    ]
  }
})

const dailyExercise = computed(() => {
  if (currentWeight.value > 80) {
    return [
      { name: '快走', cal: 150 },
      { name: '游泳', cal: 220 },
      { name: '拉伸放松', cal: 60 }
    ]
  } else {
    return [
      { name: '帕梅拉燃脂', cal: 190 },
      { name: '跳绳', cal: 280 },
      { name: '瑜伽流', cal: 120 }
    ]
  }
})

const motivationQuote = computed(() => {
  const quotes = [
    '每一个微小的努力，都在雕刻更好的自己',
    '减脂不是苦行，而是与身体的和解',
    '今天的小坚持，明天的大惊喜',
    '你流下的每一滴汗，都是对抗惰性的勋章'
  ]
  const dayIndex = new Date().getDate() % quotes.length
  return quotes[dayIndex]
})

// ---------- 方法 ----------
function openGoalModal() {
  tempGoalWeight.value = goalWeight.value.toString()
  showGoalModal.value = true
}
function openRecordModal() {
  tempWeight.value = ''
  showRecordModal.value = true
}

function updateGoalWeight() {
  let newGoal = parseFloat(tempGoalWeight.value)
  if (isNaN(newGoal) || newGoal <= 0) {
    uni.showToast({ title: '请输入有效体重', icon: 'none' })
    return
  }
  if (newGoal >= currentWeight.value) {
    uni.showToast({ title: '目标体重需小于当前体重', icon: 'none' })
    return
  }
  goalWeight.value = newGoal
  saveData()
  showGoalModal.value = false
  uni.showToast({ title: '目标已更新', icon: 'success' })
}

function addWeightRecord() {
  let newWeight = parseFloat(tempWeight.value)
  if (isNaN(newWeight) || newWeight <= 0 || newWeight > 300) {
    uni.showToast({ title: '请输入正确的体重', icon: 'none' })
    return
  }
  const now = new Date()
  const dateStr = formatDate(now)
  const existingIndex = weightRecords.value.findIndex(record => record.dateStr === dateStr)
  if (existingIndex !== -1) {
    uni.showModal({
      title: '提示',
      content: '今日已有体重记录，是否覆盖？',
      success: (res) => {
        if (res.confirm) {
          weightRecords.value[existingIndex].weight = newWeight
          weightRecords.value[existingIndex].date = now.getTime()
          updateCurrentFromRecords()
          saveData()
          uni.showToast({ title: '更新成功', icon: 'success' })
        }
      }
    })
  } else {
    weightRecords.value.push({
      date: now.getTime(),
      weight: newWeight,
      dateStr: dateStr
    })
    updateCurrentFromRecords()
    saveData()
    uni.showToast({ title: '记录成功', icon: 'success' })
  }
  showRecordModal.value = false
  tempWeight.value = ''
}

function goBack() {
  uni.navigateBack()
}

// 页面生命周期：每次显示时重新加载数据（确保多设备同步）
onShow(() => {
  if (!isLoggedIn.value) {
    uni.showModal({
      title: '提示',
      content: '请先登录',
      success: () => {
        uni.navigateBack()
      }
    })
    return
  }
  loadData()
})
</script>

<style scoped>
.weightloss-container {
  min-height: 100vh;
  background: linear-gradient(145deg, #f0f9f4 0%, #e4f0ea 100%);
  box-sizing: border-box;
}

.custom-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 88rpx 32rpx 24rpx;
  background: rgba(255,255,245,0.92);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(120,160,120,0.2);
}

.nav-back {
  width: 64rpx;
  height: 64rpx;
  background: rgba(100,140,100,0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.back-icon { font-size: 48rpx; color: #2c5e2e; font-weight: 600; }
.nav-title { font-size: 36rpx; font-weight: 700; background: linear-gradient(135deg, #2b5e2b, #6f9e6f); -webkit-background-clip: text; color: transparent; }
.nav-placeholder { width: 64rpx; }

.scroll-content {
  padding: 24rpx 32rpx;
  height: calc(100vh - 140rpx);
  box-sizing: border-box;
  overflow-y: auto;
  overflow-x: hidden;
}

/* 隐藏滚动条，确保右侧边距视觉统一 */
.scroll-content::-webkit-scrollbar {
  display: none;
  width: 0;
  background: transparent;
}

.stats-card {
  background: rgba(250,255,245,0.85);
  backdrop-filter: blur(16px);
  border-radius: 56rpx;
  padding: 32rpx;
  margin-bottom: 32rpx;
  box-shadow: 0 12rpx 32rpx rgba(60, 90, 60, 0.08);
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 32rpx;
}
.stats-label { font-size: 28rpx; font-weight: 600; color: #3d6b3d; }
.goal-edit { display: flex; gap: 8rpx; background: #e9f3e6; padding: 10rpx 20rpx; border-radius: 48rpx; }
.edit-icon { font-size: 26rpx; }
.edit-text { font-size: 24rpx; color: #3b7a3b; }

.weight-progress-area {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32rpx;
}
.weight-item { text-align: center; }
.weight-value { font-size: 56rpx; font-weight: 800; color: #2d4a2d; line-height: 1.2; }
.weight-unit { font-size: 26rpx; color: #6b8c6b; margin-left: 6rpx; }
.weight-label { font-size: 24rpx; color: #6c8f6c; display: block; margin-top: 6rpx; }

.progress-ring-wrapper {
  width: 160rpx;
  height: 160rpx;
}
.progress-ring {
  position: relative;
  width: 100%;
  height: 100%;
}
.ring-bg, .ring-fill {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
}
.ring-bg { background: #e0ecd8; }
.ring-fill {
  background: conic-gradient(#45b787 0deg, #45b787 var(--angle, 0deg), transparent var(--angle, 0deg));
  transform-origin: 50% 50%;
  clip: rect(0, 160rpx, 160rpx, 80rpx);
}
.ring-inner {
  position: absolute;
  top: 20rpx;
  left: 20rpx;
  width: 120rpx;
  height: 120rpx;
  background: white;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.progress-percent { font-size: 32rpx; font-weight: 800; color: #2f6b47; }
.progress-text { font-size: 20rpx; color: #7ea37e; }

.summary-row {
  display: flex;
  justify-content: space-around;
  background: #f4fbf0;
  border-radius: 48rpx;
  padding: 20rpx 0;
}
.summary-item { text-align: center; flex:1; }
.summary-number { font-size: 40rpx; font-weight: 800; color: #346d34; }
.summary-desc { font-size: 24rpx; color: #568a56; margin-left: 8rpx; }
.summary-divider { width: 1px; background: #bfdbc0; height: 40rpx; align-self: center; }

.record-card {
  background: #ffffffcc;
  backdrop-filter: blur(12px);
  border-radius: 48rpx;
  padding: 28rpx;
  margin-bottom: 32rpx;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28rpx;
}
.card-title { font-size: 32rpx; font-weight: 700; color: #3b6e3b; }
.add-record-btn { background: #cfead0; padding: 12rpx 24rpx; border-radius: 60rpx; display: flex; gap: 6rpx; }
.add-icon { font-size: 32rpx; font-weight: bold; color: #2c6e2c; }
.add-text { font-size: 26rpx; color: #2f6b2f; }

.record-list { display: flex; flex-direction: column; gap: 20rpx; }
.record-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8fff4;
  padding: 18rpx 24rpx;
  border-radius: 80rpx;
}
.record-date { display: flex; flex-direction: column; align-items: center; gap: 4rpx; }
.date-day { font-size: 32rpx; font-weight: 700; color: #2b522b; }
.date-month { font-size: 22rpx; color: #819b81; }
.record-weight-info { display: flex; align-items: baseline; gap: 20rpx; }
.record-weight { font-size: 36rpx; font-weight: 700; color: #1f4a1f; }
.record-trend { font-size: 24rpx; font-weight: 600; padding: 4rpx 12rpx; border-radius: 32rpx; }
.trend-down { background: #d4edc9; color: #367c36; }
.trend-up { background: #ffe1cf; color: #c95c0c; }
.trend-steady { background: #e9eef0; color: #5c7a5c; }

.empty-records { text-align: center; padding: 48rpx; }
.trend-tip { margin-top: 24rpx; background: #eaffea; border-radius: 56rpx; padding: 16rpx 24rpx; display: flex; gap: 12rpx; align-items: center; }

.recommend-grid {
  display: flex;
  gap: 28rpx;
  margin-bottom: 32rpx;
}
.rec-card {
  flex: 1;
  background: rgba(248,255,240,0.85);
  backdrop-filter: blur(12px);
  border-radius: 44rpx;
  padding: 28rpx 20rpx;
}
.rec-header { display: flex; align-items: center; gap: 12rpx; margin-bottom: 24rpx; }
.rec-icon { font-size: 40rpx; }
.rec-title { font-size: 30rpx; font-weight: 700; color: #476b47; }
.food-list, .exercise-list { display: flex; flex-direction: column; gap: 16rpx; }
.food-item, .exercise-item { display: flex; justify-content: space-between; background: #ffffffaa; padding: 12rpx 20rpx; border-radius: 60rpx; }
.calorie-tip, .encourage-text { margin-top: 20rpx; font-size: 22rpx; text-align: center; color: #6e936e; background: #e5f2df; border-radius: 48rpx; padding: 12rpx; }

.motivation-card {
  background: linear-gradient(105deg, #daeed2, #cae3c2);
  border-radius: 60rpx;
  padding: 32rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  margin-bottom: 32rpx;
}
.quote-text { font-size: 28rpx; font-weight: 500; color: #2f6a3a; text-align: center; flex: 1; }
.quote-icon { font-size: 36rpx; }

/* 自定义弹窗样式 */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.popup-container {
  width: 560rpx;
  background: #fff9f2;
  border-radius: 64rpx;
  padding: 48rpx 40rpx;
  text-align: center;
}
.popup-title { font-size: 36rpx; font-weight: 700; color: #2a6230; display: block; margin-bottom: 36rpx; }
.popup-input-area { margin-bottom: 48rpx; text-align: left; }
.input-label { font-size: 28rpx; color: #5e7a5e; margin-bottom: 12rpx; display: block; }
.popup-input { background: #f3f9f0; border-radius: 56rpx; height: 84rpx; padding: 0 28rpx; font-size: 32rpx; border: 1px solid #cbdbc6; }
.popup-buttons { display: flex; gap: 24rpx; }
.popup-btn { flex: 1; height: 80rpx; border-radius: 60rpx; font-size: 28rpx; border: none; }
.cancel { background: #eef2ec; color: #4d6e4d; }
.confirm { background: #48944a; color: white; }

.bottom-safe { height: 40rpx; }
</style>