<template>
  <view class="container">
    <!-- 久坐提醒卡片 -->
    <view class="card">
      <view class="card-header">
        <text class="card-icon">🪑</text>
        <text class="card-title">久坐提醒</text>
      </view>
      <view class="reminder-settings">
        <view class="setting-item">
          <text class="setting-label">提醒间隔</text>
          <view class="interval-selector">
            <button class="interval-btn" :class="{ active: interval === 30 }" @click="updateInterval(30)">30分钟</button>
            <button class="interval-btn" :class="{ active: interval === 45 }" @click="updateInterval(45)">45分钟</button>
            <button class="interval-btn" :class="{ active: interval === 60 }" @click="updateInterval(60)">60分钟</button>
          </view>
        </view>
        <button class="toggle-btn" :class="{ active: reminderEnabled }" @click="toggleReminder">
          {{ reminderEnabled ? '✔ 提醒已开启' : '⏸ 提醒已关闭' }}
        </button>
      </view>
      <view v-if="reminderEnabled" class="reminder-note">
        <text>💡 每 {{ interval }} 分钟会提醒您起身活动</text>
      </view>
    </view>

    <!-- 饮水提示卡片 -->
    <view class="card">
      <view class="card-header">
        <text class="card-icon">💧</text>
        <text class="card-title">饮水提示</text>
      </view>
      <view class="water-stats">
        <view class="water-progress-wrap">
          <text class="water-amount">{{ waterIntake }} ml</text>
          <view class="progress-bar">
            <view class="progress-fill water-fill" :style="{ width: waterPercent + '%' }"></view>
          </view>
          <text class="water-target">目标 {{ waterTarget }} ml</text>
        </view>
        <view class="water-actions">
          <button class="water-btn small" @click="addWater(250)">+ 250ml</button>
          <button class="water-btn small" @click="addWater(500)">+ 500ml</button>
          <button class="water-btn outline" @click="resetWater">重置</button>
        </view>
        <view class="custom-water">
          <input type="number" v-model="customAmount" placeholder="自定义 (ml)" class="custom-input" />
          <button class="water-btn" @click="addWater(customAmount)">添加</button>
        </view>
      </view>
    </view>

    <!-- 今日健康小贴士 -->
    <view class="tip-card">
      <text class="tip-icon">✨</text>
      <text class="tip-text">久坐每45分钟起来活动2分钟，能显著降低健康风险。保持饮水充足，提高工作效率！</text>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

// 久坐相关
const interval = ref(45)
const reminderEnabled = ref(false)
let timer = null

// 饮水相关
const waterIntake = ref(0)
const waterTarget = ref(2000)
const customAmount = ref('')

const waterPercent = computed(() => Math.min(100, (waterIntake.value / waterTarget.value) * 100))

// 本地存储 key
const STORAGE_WATER = 'work_water_intake'
const STORAGE_WATER_DATE = 'work_water_date'
const STORAGE_REMINDER_ENABLED = 'work_reminder_enabled'
const STORAGE_INTERVAL = 'work_interval'

function initData() {
  // 久坐提醒
  const savedEnabled = uni.getStorageSync(STORAGE_REMINDER_ENABLED)
  const savedInterval = uni.getStorageSync(STORAGE_INTERVAL)
  reminderEnabled.value = savedEnabled === true
  if (typeof savedInterval === 'number' && !isNaN(savedInterval)) {
    interval.value = savedInterval
  } else {
    interval.value = 45
  }

  // 饮水数据（按天重置）
  const lastDate = uni.getStorageSync(STORAGE_WATER_DATE)
  const today = new Date().toDateString()
  if (lastDate !== today) {
    waterIntake.value = 0
    uni.setStorageSync(STORAGE_WATER_DATE, today)
    uni.setStorageSync(STORAGE_WATER, 0)
  } else {
    let savedWater = uni.getStorageSync(STORAGE_WATER)
    if (typeof savedWater !== 'number' || isNaN(savedWater)) savedWater = 0
    waterIntake.value = savedWater
  }
}

function saveWater() {
  uni.setStorageSync(STORAGE_WATER, waterIntake.value)
}

function addWater(ml) {
  if (ml === undefined || ml === null) return
  let num = parseFloat(ml)
  if (isNaN(num) || num <= 0) {
    uni.showToast({ title: '请输入有效毫升数', icon: 'none' })
    return
  }
  waterIntake.value += num
  saveWater()
  uni.showToast({ title: `已添加 ${num}ml 饮水`, icon: 'success' })
  if (waterIntake.value >= waterTarget.value) {
    uni.showToast({ title: '恭喜完成今日饮水目标！', icon: 'success' })
  }
  customAmount.value = ''
}

function resetWater() {
  waterIntake.value = 0
  saveWater()
  uni.showToast({ title: '今日饮水量已重置', icon: 'none' })
}

function updateInterval(min) {
  interval.value = min
  uni.setStorageSync(STORAGE_INTERVAL, min)
  if (reminderEnabled.value) {
    stopReminder()
    startReminder()
  }
}

function toggleReminder() {
  reminderEnabled.value = !reminderEnabled.value
  uni.setStorageSync(STORAGE_REMINDER_ENABLED, reminderEnabled.value)
  if (reminderEnabled.value) {
    startReminder()
    uni.showToast({ title: `久坐提醒已开启，每${interval.value}分钟提醒一次`, icon: 'success' })
  } else {
    stopReminder()
    uni.showToast({ title: '久坐提醒已关闭', icon: 'none' })
  }
}

function startReminder() {
  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    if (reminderEnabled.value) {
      uni.showToast({
        title: '该起来活动一下了！\n走动2分钟，保护颈椎和腰椎',
        icon: 'none',
        duration: 4000
      })
      uni.vibrateShort({ type: 'light' })
    }
  }, interval.value * 60 * 1000)
}

function stopReminder() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(() => {
  initData()
  if (reminderEnabled.value) startReminder()
})

onUnmounted(() => {
  stopReminder()
})
</script>

<style scoped>
.container {
  padding: 30rpx;
  background-color: #f5f7fa;
  min-height: 100vh;
}

/* 卡片样式（与健身界面一致） */
.card {
  background: white;
  border-radius: 32rpx;
  padding: 30rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 8rpx 20rpx rgba(0,0,0,0.05);
}
.card-header {
  display: flex;
  align-items: center;
  margin-bottom: 30rpx;
  border-left: 8rpx solid #409eff;
  padding-left: 20rpx;
}
.card-icon {
  font-size: 48rpx;
  margin-right: 12rpx;
}
.card-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #2c3e50;
}

/* 久坐设置 */
.reminder-settings {
  display: flex;
  flex-direction: column;
  gap: 30rpx;
}
.setting-item {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.setting-label {
  font-size: 28rpx;
  color: #606266;
}
.interval-selector {
  display: flex;
  gap: 20rpx;
}
.interval-btn {
  flex: 1;
  background-color: #f0f2f5;
  border-radius: 48rpx;
  height: 70rpx;
  line-height: 70rpx;
  font-size: 28rpx;
  color: #606266;
  border: none;
}
.interval-btn.active {
  background-color: #409eff;
  color: white;
}
.toggle-btn {
  background-color: #e4e7ed;
  color: #909399;
  border-radius: 48rpx;
  height: 80rpx;
  line-height: 80rpx;
  font-size: 32rpx;
  border: none;
}
.toggle-btn.active {
  background: linear-gradient(135deg, #67c23a, #5daf34);
  color: white;
}
.reminder-note {
  margin-top: 20rpx;
  font-size: 26rpx;
  color: #e6a23c;
  text-align: center;
}

/* 饮水区域 */
.water-stats {
  display: flex;
  flex-direction: column;
  gap: 30rpx;
}
.water-progress-wrap {
  text-align: center;
}
.water-amount {
  font-size: 56rpx;
  font-weight: bold;
  color: #409eff;
  display: block;
  margin-bottom: 16rpx;
}
.progress-bar {
  background-color: #e0e0e0;
  border-radius: 16rpx;
  height: 16rpx;
  overflow: hidden;
  margin: 20rpx 0;
}
.progress-fill {
  height: 100%;
  width: 0%;
  transition: width 0.3s;
}
.water-fill {
  background-color: #409eff;
}
.water-target {
  font-size: 26rpx;
  color: #909399;
}
.water-actions {
  display: flex;
  gap: 20rpx;
  justify-content: center;
}
.water-btn {
  flex: 1;
  background-color: #ecf5ff;
  color: #409eff;
  border-radius: 48rpx;
  height: 70rpx;
  line-height: 70rpx;
  font-size: 28rpx;
  border: none;
}
.water-btn.small {
  flex: 0 1 auto;
  padding: 0 30rpx;
}
.water-btn.outline {
  background-color: white;
  border: 1px solid #dcdfe6;
  color: #606266;
}
.custom-water {
  display: flex;
  gap: 20rpx;
  align-items: center;
}
.custom-input {
  flex: 2;
  background-color: #f5f7fa;
  border-radius: 48rpx;
  height: 70rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
  border: 1px solid #e4e7ed;
}
.custom-water .water-btn {
  flex: 1;
}

.tip-card {
  background: linear-gradient(135deg, #fff9e6, #fff4d9);
  border-radius: 24rpx;
  padding: 30rpx;
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-top: 20rpx;
}
.tip-icon {
  font-size: 48rpx;
}
.tip-text {
  flex: 1;
  font-size: 28rpx;
  color: #b7791f;
  line-height: 1.4;
}
</style>