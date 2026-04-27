<template>
  <view class="container">
    <!-- 未登录：显示登录/注册表单 -->
    <view v-if="!isLoggedIn" class="auth-card">
      <input 
        class="auth-input" 
        v-model="account" 
        placeholder="账号" 
        placeholder-class="input-placeholder"
      />
      <view class="password-wrapper">
        <input 
          class="auth-input password-input" 
          v-model="password" 
          :password="!showPassword"
          placeholder="密码" 
          placeholder-class="input-placeholder"
        />
        <view class="eye-icon" @click="togglePasswordVisibility">
          <u-icon :name="showPassword ? 'eye' : 'eye-close'" size="20" color="#909399"></u-icon>
        </view>
      </view>
      <view class="auth-actions">
        <button class="auth-btn primary" @click="handleLogin">登录</button>
        <button class="auth-btn secondary" @click="handleRegister">注册</button>
      </view>
      <text v-if="authError" class="error">{{ authError }}</text>
    </view>

    <!-- 已登录：显示数据看板 -->
    <view v-else class="dashboard">
      <view class="user-bar">
        <text>你好，{{ username }}</text>
        <button size="mini" type="warn" @click="logout">退出</button>
      </view>

      <!-- 快速添加入口 -->
      <view class="add-buttons">
        <button size="mini" @click="navigateTo('workout/add')">➕ 运动</button>
        <button size="mini" @click="navigateTo('sleep/add')">😴 睡眠</button>
        <button size="mini" @click="navigateTo('diet/add')">🍽️ 饮食</button>
      </view>

      <!-- 今日统计 -->
      <StatsCard title="今日数据" :stats="todayStats" />
      <!-- 本周趋势（简单显示） -->
      <StatsCard title="本周累计" :stats="weeklyStats" />
      <!-- 总计统计 -->
      <StatsCard title="总计" :stats="totalStats" />

      <!-- 综合报告 + 异常建议 -->
      <ReportCard :report="dailyReport" :advice="advice" />

      <view v-if="loading" class="loading">加载中...</view>
      <text v-if="errorMsg" class="error">{{ errorMsg }}</text>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '@/store/user'
import { auth, statsApi } from '@/utils/api'
import StatsCard from '@/components/StatsCard.vue'
import ReportCard from '@/components/ReportCard.vue'

const { state, setUser, clearUser, isLoggedIn } = useUserStore()
const username = ref(state.username)
const account = ref('demo')
const password = ref('demo123')
const authError = ref('')
const loading = ref(false)
const errorMsg = ref('')

// 密码显示切换
const showPassword = ref(false)
function togglePasswordVisibility() {
  showPassword.value = !showPassword.value
}

// 统计数据
const todayStats = ref({
  workoutMinutes: 0,
  workoutTarget: 30,
  sleepHours: 0,
  sleepTarget: 8,
  dietCalories: 0,
  dietTarget: 2000
})
const weeklyStats = ref({ workoutTotal: 0, sleepTotal: 0, dietTotal: 0 })
const totalStats = ref({ workoutCount: 0, workoutMinutes: 0, sleepCount: 0, dietCount: 0 })
const dailyReport = ref({ score: 0, details: '' })
const advice = ref('')

// 加载所有数据
async function loadDashboard() {
  if (!isLoggedIn.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const [today, weekly, summary] = await Promise.all([
      statsApi.today(),
      statsApi.weekly(),
      statsApi.summary()
    ])
    todayStats.value = {
      workoutMinutes: today.workoutMinutes || 0,
      workoutTarget: today.workoutTarget || 30,
      sleepHours: today.sleepHours || 0,
      sleepTarget: today.sleepTarget || 8,
      dietCalories: today.dietCalories || 0,
      dietTarget: today.dietTarget || 2000
    }
    weeklyStats.value = weekly
    totalStats.value = summary
    generateReportAndAdvice()
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

// 模拟联动分析（可替换为后端接口 /report/daily）
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

  dailyReport.value = {
    score: totalScore,
    details: `运动${workoutScore.toFixed(0)}分，睡眠${sleepScore.toFixed(0)}分，饮食${dietScore.toFixed(0)}分`
  }

  let adviceText = ''
  if (s < 6) adviceText += '睡眠严重不足，建议今晚提前休息。'
  if (w > wTarget * 1.5 && s < 7) adviceText += '运动过量且睡眠不足，请降低强度。'
  if (d > dTarget) adviceText += '今日热量超标，下一餐宜清淡。'
  if (!adviceText) adviceText = '各项指标良好，继续保持！'
  advice.value = adviceText
}

async function handleLogin() {
  authError.value = ''
  try {
    const res = await auth.login(account.value, password.value)
    setUser(res.token, res.user.account)
    username.value = res.user.account
    await loadDashboard()
    uni.showToast({ title: '登录成功', icon: 'success' })
  } catch (e) {
    authError.value = e.message
    uni.showToast({ title: e.message, icon: 'none' })
  }
}

async function handleRegister() {
  authError.value = ''
  try {
    const res = await auth.register(account.value, password.value)
    setUser(res.token, res.user.account)
    username.value = res.user.account
    await loadDashboard()
    uni.showToast({ title: '注册成功', icon: 'success' })
  } catch (e) {
    authError.value = e.message
    uni.showToast({ title: e.message, icon: 'none' })
  }
}

function logout() {
  clearUser()
  username.value = ''
  todayStats.value = {
    workoutMinutes: 0,
    workoutTarget: 30,
    sleepHours: 0,
    sleepTarget: 8,
    dietCalories: 0,
    dietTarget: 2000
  }
  weeklyStats.value = { workoutTotal: 0, sleepTotal: 0, dietTotal: 0 }
  totalStats.value = { workoutCount: 0, workoutMinutes: 0, sleepCount: 0, dietCount: 0 }
  dailyReport.value = { score: 0, details: '' }
  advice.value = ''
  uni.showToast({ title: '已退出', icon: 'none' })
}

function navigateTo(page) {
  uni.navigateTo({ url: `/pages/${page}` })
}

onMounted(() => {
  if (isLoggedIn.value) {
    loadDashboard()
  }
})
</script>

<style scoped>
.container { padding: 20rpx; }

/* 登录卡片样式 */
.auth-card {
  margin-top: 120rpx;
  padding: 50rpx 40rpx;
  background: white;
  border-radius: 32rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.05);
}

/* 输入框样式 */
.auth-input {
  width: 100%;
  height: 88rpx;
  padding: 0 24rpx;
  margin-bottom: 32rpx;
  font-size: 32rpx;
  background-color: #f5f7fa;
  border-radius: 16rpx;
  border: 1px solid #e4e7ed;
  box-sizing: border-box;
  transition: all 0.2s;
}

.auth-input:focus {
  border-color: #409eff;
  background-color: #fff;
}

/* placeholder 样式 */
.input-placeholder {
  color: #c0c4cc;
  font-size: 28rpx;
}

/* 密码显示切换容器 */
.password-wrapper {
  position: relative;
  width: 100%;
}
.password-input {
  padding-right: 70rpx;
  margin-bottom: 0;  /* 覆盖默认 margin-bottom，因为外层 auth-input 已经有 margin-bottom */
}
.eye-icon {
  position: absolute;
  right: 20rpx;
  top: 50%;
  transform: translateY(-50%);
  width: 60rpx;
  height: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9;
  font-size: 40rpx;
  color: #909399;
}

/* 按钮容器 */
.auth-actions {
  display: flex;
  gap: 24rpx;
  margin-top: 40rpx;
}

/* 按钮通用样式 */
.auth-btn {
  flex: 1;
  height: 88rpx;
  line-height: 88rpx;
  border-radius: 48rpx;
  font-size: 32rpx;
  font-weight: 500;
  border: none;
}

.auth-btn.primary {
  background: linear-gradient(135deg, #409eff, #2c6ed1);
  color: white;
}

.auth-btn.secondary {
  background: #f0f2f5;
  color: #606266;
  border: 1px solid #dcdfe6;
}

/* 仪表盘样式 */
.dashboard { display: flex; flex-direction: column; gap: 20rpx; }
.user-bar { display: flex; justify-content: space-between; align-items: center; }
.add-buttons { display: flex; gap: 20rpx; justify-content: space-around; margin: 20rpx 0; }
.error { color: red; font-size: 28rpx; margin-top: 20rpx; display: block; }
.loading { text-align: center; color: gray; }
</style>