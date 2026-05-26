<template>
  <view class="pomodoro-page">
    <view class="pomodoro-card">
      <view class="timer-display">
        <text class="timer-minutes">{{ formattedTime.minutes }}</text>
        <text class="timer-colon">:</text>
        <text class="timer-seconds">{{ formattedTime.seconds }}</text>
      </view>
      <view class="timer-status">
        <text class="status-text">{{ isWorking ? '专注中' : '休息中' }}</text>
      </view>
      <view class="timer-controls">
        <button v-if="!isTimerRunning" class="timer-btn start" @click="startTimer">开始专注</button>
        <button v-if="isTimerRunning" class="timer-btn pause" @click="pauseTimer">暂停</button>
        <button v-if="isTimerRunning" class="timer-btn reset" @click="resetTimer">重置</button>
      </view>
      <view class="pomodoro-stats">
        <text>今日已完成 {{ todayPomodoros }} 个番茄钟</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { workApi } from '@/utils/api'

const WORK_DURATION = 25 * 60
const BREAK_DURATION = 5 * 60
let timerInterval = null
const isWorking = ref(true)
const remainingSeconds = ref(WORK_DURATION)
const isTimerRunning = ref(false)
const todayPomodoros = ref(0)

const formattedTime = computed(() => {
  const mins = Math.floor(remainingSeconds.value / 60)
  const secs = remainingSeconds.value % 60
  return { minutes: String(mins).padStart(2, '0'), seconds: String(secs).padStart(2, '0') }
})

const tick = async () => {
  if (remainingSeconds.value <= 1) {
    if (isWorking.value) {
      isWorking.value = false
      remainingSeconds.value = BREAK_DURATION
      todayPomodoros.value += 1
      uni.showToast({ title: '专注结束，休息一下', icon: 'none' })
    } else {
      isWorking.value = true
      remainingSeconds.value = WORK_DURATION
      uni.showToast({ title: '休息结束，开始新一轮', icon: 'none' })
    }
  } else {
    remainingSeconds.value--
  }
}

const loadTodayStats = async () => {
  try {
    const todayStats = await workApi.getTodayStats()
    if (todayStats) {
      todayPomodoros.value = todayStats.sessions || 0
    }
  } catch (error) {
    console.warn('加载今日统计失败', error)
  }
}

const startTimer = async () => {
  if (isTimerRunning.value) return
  isTimerRunning.value = true
  timerInterval = setInterval(tick, 1000)
}

const pauseTimer = () => {
  if (!isTimerRunning.value) return
  clearInterval(timerInterval)
  timerInterval = null
  isTimerRunning.value = false
}

const resetTimer = () => {
  pauseTimer()
  isWorking.value = true
  remainingSeconds.value = WORK_DURATION
}

onMounted(async () => {
  await loadTodayStats()
})

onUnmounted(() => {
  if (timerInterval) {
    clearInterval(timerInterval)
  }
})
</script>

<style scoped>
.pomodoro-page {
  min-height: 100vh;
  padding: 30rpx;
  background: linear-gradient(180deg, #f7fbff 0%, #e8f4ff 100%);
}
.pomodoro-card {
  background: rgba(255,255,255,0.98);
  border-radius: 48rpx;
  padding: 40rpx 30rpx;
  box-shadow: 0 20rpx 40rpx rgba(0,0,0,0.08);
}
.timer-display {
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(145deg, #e0f2fe, #dbeafe);
  padding: 30rpx;
  border-radius: 120rpx;
  margin-bottom: 30rpx;
}
.timer-minutes, .timer-seconds {
  font-size: 96rpx;
  font-weight: 800;
  background: linear-gradient(135deg, #0ea5e9, #3b82f6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.timer-colon {
  font-size: 88rpx;
  font-weight: 700;
  color: #0ea5e9;
  margin: 0 8rpx;
}
.timer-status {
  text-align: center;
  margin-bottom: 24rpx;
}
.status-text {
  font-size: 30rpx;
  font-weight: 700;
  color: #2563eb;
  background: rgba(219,234,254,0.9);
  padding: 10rpx 30rpx;
  border-radius: 60rpx;
}
.timer-controls {
  display: flex;
  justify-content: space-around;
  gap: 20rpx;
  margin-bottom: 24rpx;
}
.timer-btn {
  flex: 1;
  height: 80rpx;
  border-radius: 48rpx;
  border: none;
  font-size: 30rpx;
  font-weight: 700;
  color: #fff;
}
.timer-btn.start {
  background: linear-gradient(135deg, #38bdf8, #0ea5e9);
}
.timer-btn.pause {
  background: linear-gradient(135deg, #f97316, #ea580c);
}
.timer-btn.reset {
  background: linear-gradient(135deg, #f43f5e, #e11d48);
}
.pomodoro-stats {
  text-align: center;
  margin-top: 20rpx;
  font-size: 28rpx;
  color: #334155;
}
</style>