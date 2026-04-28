<template>
  <view class="container">
    <!-- ========= 未登录：显示登录/注册表单 ========= -->
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
          <text>{{ showPassword ? '🙈' : '👁️' }}</text>
        </view>
      </view>
      <view class="auth-actions">
        <button class="auth-btn primary" @click="handleLogin">登录</button>
        <button class="auth-btn secondary" @click="handleRegister">注册</button>
      </view>
      <text v-if="authError" class="error">{{ authError }}</text>
    </view>

    <!-- ========= 已登录：主面板（纯原生实现） ========= -->
    <view v-else class="dashboard">
      <!-- 顶部用户栏 -->
      <view class="user-bar">
        <text class="greeting">你好，{{username}}</text>
        <button class="logout-btn" @click="logout">退出</button>
      </view>

      <!-- 综合健康指数卡片 -->
      <view class="score-card">
        <view class="score-left">
          <text class="score-label">今日健康指数</text>
          <text class="score-number">{{ dailyReport.score }}</text>
          <text class="score-unit">分</text>
        </view>
        <!-- 简易环形进度条（百分比填充） -->
        <view class="score-ring">
          <view class="ring-bg"></view>
          <view class="ring-fill" :style="{ height: dailyReport.score + '%' }"></view>
          <text class="ring-text">{{ dailyReport.score }}%</text>
        </view>
      </view>

      <!-- 三个指标卡片 -->
      <view class="stats-grid">
        <!-- 运动 -->
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
        <!-- 睡眠 -->
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
        <!-- 饮食 -->
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

      <!-- 智能建议 -->
      <view class="advice-card">
        <text class="advice-icon">💡</text>
        <text class="advice-text">{{ advice }}</text>
      </view>

      <!-- 快捷操作区域 -->
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
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/store/user'
import { auth, statsApi } from '@/utils/api'

// 用户状态
const { state, setUser, clearUser, isLoggedIn } = useUserStore()
const username = ref(state.username)

// 登录表单
const account = ref('demo')
const password = ref('demo123')
const authError = ref('')
const showPassword = ref(false)

// 主面板数据
const loading = ref(false)
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

// 计算百分比
const workoutPercent = computed(() => Math.min(100, (todayStats.value.workoutMinutes / todayStats.value.workoutTarget) * 100))
const sleepPercent = computed(() => Math.min(100, (todayStats.value.sleepHours / todayStats.value.sleepTarget) * 100))
const dietPercent = computed(() => {
  const consumed = todayStats.value.dietCalories
  const target = todayStats.value.dietTarget
  return consumed >= target ? 100 : (consumed / target) * 100
})

// 切换密码可见性
function togglePasswordVisibility() {
  showPassword.value = !showPassword.value
}

// 登录
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

// 注册
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

// 加载主面板数据
async function loadDashboard() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    const [today] = await Promise.all([statsApi.today()])
    todayStats.value = {
      workoutMinutes: today.workoutMinutes || 0,
      workoutTarget: today.workoutTarget || 30,
      sleepHours: today.sleepHours || 0,
      sleepTarget: today.sleepTarget || 8,
      dietCalories: today.dietCalories || 0,
      dietTarget: today.dietTarget || 2000
    }
    generateReportAndAdvice()
  } catch (e) {
    uni.showToast({ title: e.message, icon: 'none' })
  } finally {
    loading.value = false
  }
}

// 生成报告和建议
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

// 退出登录
function logout() {
  clearUser()
  // 重置数据
  todayStats.value = {
    workoutMinutes: 0,
    workoutTarget: 30,
    sleepHours: 0,
    sleepTarget: 8,
    dietCalories: 0,
    dietTarget: 2000
  }
  dailyReport.value.score = 0
  advice.value = ''
  uni.showToast({ title: '已退出', icon: 'none' })
}

// 页面跳转
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
.container {
  padding: 30rpx;
  background-color: #f5f7fa;
  min-height: 100vh;
}

/* ========= 登录表单样式 ========= */
.auth-card {
  margin-top: 120rpx;
  padding: 50rpx 40rpx;
  background: white;
  border-radius: 32rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.05);
}
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
}
.password-wrapper {
  position: relative;
  width: 100%;
}
.password-input {
  padding-right: 70rpx;
  margin-bottom: 0;
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
  font-size: 40rpx;
  color: #909399;
}
.auth-actions {
  display: flex;
  gap: 24rpx;
  margin-top: 40rpx;
}
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
.error {
  color: red;
  font-size: 28rpx;
  margin-top: 20rpx;
  display: block;
}

/* ========= 主面板样式 ========= */
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 30rpx;
}
.user-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.greeting {
  font-size: 36rpx;
  font-weight: bold;
  color: #303133;
}
.logout-btn {
  background-color: #f56c6c;
  color: white;
  border: none;
  border-radius: 40rpx;
  padding: 8rpx 24rpx;
  font-size: 28rpx;
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

/* 三指标卡片 */
.stats-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
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

/* 建议卡片 */
.advice-card {
  background: #ecf5ff;
  border-radius: 24rpx;
  padding: 24rpx;
  display: flex;
  align-items: center;
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

/* 快捷操作按钮 */
.action-buttons {
  display: flex;
  gap: 20rpx;
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