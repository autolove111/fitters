<template>
  <view class="container" :class="{ dark: isDark }">
    <!-- ========= 未登录：显示登录/注册表单 ========= -->
    <view v-if="!isLoggedIn" class="auth-card">
      <view class="logo-area">
        <text class="logo-icon">✨</text>
        <text class="logo-title">Fitters 健康管家</text>
        <text class="logo-sub">极致 · 平衡 · 生命力</text>
      </view>

      <input 
        class="auth-input" 
        v-model="account" 
        placeholder="账号 / 邮箱" 
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
        <view class="toggle-pwd-btn" @click="togglePasswordVisibility">
          <text>{{ showPassword ? '隐藏' : '显示' }}</text>
        </view>
      </view>
      <view class="auth-actions">
        <button class="auth-btn primary" @click="handleLogin">登录</button>
        <button class="auth-btn secondary" @click="handleRegister">注册</button>
      </view>
      <text v-if="authError" class="error">{{ authError }}</text>
    </view>

    <!-- ========= 已登录：卡片仪表板 ========= -->
    <view v-else class="dashboard">
      <!-- 顶部用户栏 -->
      <view class="user-bar">
        <view class="user-info">
          <view class="avatar-ring" @click="viewAvatar">
            <image v-if="userAvatar" class="avatar-img" :src="userAvatar" mode="aspectFill" />
            <text v-else class="avatar-emoji">🧘</text>
          </view>
          <view class="user-text">
            <text class="greeting">🌿 你好，{{ displayName }}</text>
            <text class="today-date">{{ currentDate }}</text>
          </view>
        </view>
        <button class="profile-btn" @click="goProfile">个人中心</button>
      </view>

      <!-- 功能卡片网格（2列） -->
      <view class="menu-grid">
        <view class="menu-card card-fitness" @click="goFitness">
          <view class="card-glow"></view>
          <view class="card-icon-wrapper">
            <text class="card-icon">❤️</text>
          </view>
          <text class="card-title">健康</text>
          <text class="card-desc">综合健康管理</text>
        </view>
        <view class="menu-card card-weightloss" @click="goWeightLoss">
          <view class="card-glow"></view>
          <view class="card-icon-wrapper">
            <text class="card-icon">🥗</text>
          </view>
          <text class="card-title">减肥</text>
          <text class="card-desc">科学减脂计划</text>
        </view>
        <view class="menu-card card-wellness" @click="goWellness">
          <view class="card-glow"></view>
          <view class="card-icon-wrapper">
            <text class="card-icon">🧘</text>
          </view>
          <text class="card-title">养生</text>
          <text class="card-desc">调养身心</text>
        </view>
        <view class="menu-card card-work" @click="goWork">
          <view class="card-glow"></view>
          <view class="card-icon-wrapper">
            <text class="card-icon">💼</text>
          </view>
          <text class="card-title">工作</text>
          <text class="card-desc">效率与专注</text>
        </view>
        <view class="menu-card card-study" @click="goStudy">
          <view class="card-glow"></view>
          <view class="card-icon-wrapper">
            <text class="card-icon">📚</text>
          </view>
          <text class="card-title">学习</text>
          <text class="card-desc">学习计划与个人助手</text>
        </view>
      </view>

      <!-- 动态健康小贴士 -->
      <view class="health-tip">
        <text class="tip-icon">🌱</text>
        <text class="tip-text">{{ dailyTip }}</text>
        <text class="tip-spark">✨</text>
      </view>

      <view class="dashboard-ambient"></view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/store/user'
import { useThemeStore } from '@/store/theme'
import { auth } from '@/utils/api'

const themeStore = useThemeStore()
const { isDark } = themeStore

const userStore = useUserStore()
const { isLoggedIn, state, displayName, setUser, loadAvatar, loadProfile } = userStore

const userAvatar = computed(() => state.avatar || '')

onShow(() => {
  loadAvatar()
  loadProfile()
})

const viewAvatar = () => {
  if (!userAvatar.value) {
    uni.showToast({ title: '暂无头像', icon: 'none' })
    return
  }
  uni.previewImage({
    urls: [userAvatar.value],
    current: userAvatar.value
  })
}

// 登录表单
const account = ref('demo')
const password = ref('demo123')
const authError = ref('')
const showPassword = ref(false)

// 当前日期
const currentDate = computed(() => {
  const now = new Date()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekday = weekdays[now.getDay()]
  return `${month}.${day} · ${weekday}`
})

// 每日健康小贴士库
const tipsList = [
  '深呼吸三次，感受当下的平静',
  '喝一杯温水，唤醒身体活力',
  '伸展四肢五分钟，缓解久坐疲劳',
  '放下手机十分钟，让眼睛休息',
  '微笑一下，释放积极能量',
  '走楼梯代替电梯，多消耗卡路里',
  '记录一件感恩的小事',
  '午餐细嚼慢咽，专注每一口',
  '站立办公半小时，改善体态',
  '眺望远方，给眼睛放个假',
  '睡前冥想五分钟，提高睡眠质量',
  '主动夸奖一个人，温暖彼此',
  '整理桌面，清爽心情',
  '步行或骑行代替短途驾车']

const dailyTip = computed(() => {
  const today = new Date()
  const startOfYear = new Date(today.getFullYear(), 0, 0)
  const dayOfYear = Math.floor((today - startOfYear) / (24 * 60 * 60 * 1000))
  const index = dayOfYear % tipsList.length
  return '今日微习惯：' + tipsList[index]
})

function togglePasswordVisibility() {
  showPassword.value = !showPassword.value
}

async function handleLogin() {
  authError.value = ''
  try {
    const res = await auth.login(account.value, password.value)
    setUser(res.token, res.user.account, res.user.nickname || '', res.user.avatar || '')
    await loadProfile()
    await loadAvatar()
    uni.showToast({ title: '登录成功', icon: 'success' })
  } catch (e) {
    authError.value = e.message
    uni.showToast({ title: e.message, icon: 'none' })
  }
}

function handleRegister() {
  uni.navigateTo({ url: '/pages/register/register' })
}

function goProfile() {
  uni.navigateTo({ url: '/pages/profile/index' })
}

function goFitness() {
  uni.navigateTo({ url: '/pages/workout/workout' })
}

function goWeightLoss() {
  uni.showToast({ title: '减肥功能开发中', icon: 'none' })
}

function goWellness() {
  uni.showToast({ title: '养生功能开发中', icon: 'none' })
}

function goWork() {
  uni.navigateTo({ url: '/pages/work/work' })
}

function goStudy() {
  uni.navigateTo({ url: '/pages/study/index' })
}
</script>

<style scoped>
/* ========= CSS 变量（亮色模式） ========= */
:root {
  --bg-primary: #f8fafc;
  --bg-secondary: #f1f5f9;
  --card-bg: rgba(255, 255, 255, 0.92);
  --card-border: rgba(255, 255, 255, 0.6);
  --input-bg: rgba(255, 255, 255, 0.9);
  --input-border: #e2e8f0;
  --text-primary: #1e293b;
  --text-secondary: #475569;
}

/* ========= 暗色模式变量 ========= */
.dark {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --card-bg: rgba(30, 41, 59, 0.85);
  --card-border: rgba(255, 255, 255, 0.08);
  --input-bg: rgba(51, 65, 85, 0.9);
  --input-border: #334155;
  --text-primary: #f1f5f9;
  --text-secondary: #cbd5e1;
}

.container {
  padding: 32rpx;
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  transition: background 0.3s ease;
}

/* ========= 登录表单 ========= */
.auth-card {
  margin-top: 80rpx;
  padding: 50rpx 40rpx 60rpx;
  background: var(--card-bg);
  backdrop-filter: blur(20px);
  border-radius: 60rpx;
  box-shadow: 0 25rpx 50rpx -12rpx rgba(0, 0, 0, 0.15), 0 0 0 1rpx var(--card-border) inset;
}

.logo-area {
  text-align: center;
  margin-bottom: 48rpx;
}
.logo-icon {
  font-size: 64rpx;
  display: block;
  background: linear-gradient(135deg, #3b82f6, #1e3a8a);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin-bottom: 12rpx;
}
.logo-title {
  font-size: 44rpx;
  font-weight: 800;
  background: linear-gradient(135deg, var(--text-primary), #3b82f6);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: -0.5rpx;
  display: block;
}
.logo-sub {
  font-size: 24rpx;
  color: var(--text-secondary);
  margin-top: 12rpx;
  display: block;
  letter-spacing: 2rpx;
}

.auth-input {
  width: 100%;
  height: 96rpx;
  padding: 0 28rpx;
  margin-bottom: 32rpx;
  font-size: 32rpx;
  background: var(--input-bg);
  border-radius: 48rpx;
  border: 1.5px solid var(--input-border);
  box-sizing: border-box;
  transition: all 0.2s;
  color: var(--text-primary);
}
.auth-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 6rpx rgba(59, 130, 246, 0.15);
}

.password-wrapper {
  position: relative;
  width: 100%;
}
.password-input {
  padding-right: 140rpx;
  margin-bottom: 0;
}
.toggle-pwd-btn {
  position: absolute;
  right: 20rpx;
  top: 50%;
  transform: translateY(-50%);
  background: #eef2ff;
  padding: 10rpx 24rpx;
  border-radius: 60rpx;
  font-size: 26rpx;
  color: #3b82f6;
  font-weight: 600;
}
.dark .toggle-pwd-btn {
  background: #334155;
  color: #60a5fa;
}

.auth-actions {
  display: flex;
  gap: 24rpx;
  margin-top: 48rpx;
}
.auth-btn {
  flex: 1;
  height: 96rpx;
  line-height: 96rpx;
  border-radius: 60rpx;
  font-size: 32rpx;
  font-weight: 600;
  border: none;
}
.auth-btn.primary {
  background: linear-gradient(105deg, #2563eb, #1e40af);
  color: white;
  box-shadow: 0 12rpx 24rpx -10rpx rgba(37, 99, 235, 0.4);
}
.auth-btn.primary:active {
  transform: scale(0.97);
}
.auth-btn.secondary {
  background: var(--card-bg);
  color: var(--text-primary);
  border: 1px solid var(--input-border);
}
.error {
  color: #ef4444;
  font-size: 26rpx;
  margin-top: 24rpx;
  text-align: center;
}

/* ========= 仪表板 ========= */
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 36rpx;
  animation: fadeUp 0.5s cubic-bezier(0.2, 0.9, 0.4, 1.1);
  padding-bottom: 40rpx;
  position: relative;
  z-index: 2;
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(30rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 用户栏 */
.user-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--card-bg);
  backdrop-filter: blur(20rpx);
  border-radius: 40rpx;
  padding: 20rpx 24rpx;
  border: 1rpx solid var(--card-border);
  box-shadow: 0 8rpx 32rpx rgba(0, 0, 0, 0.05);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.avatar-ring {
  width: 80rpx;
  height: 80rpx;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  border-radius: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 16rpx -6rpx rgba(0, 0, 0, 0.1);
  overflow: hidden;
}
.avatar-img {
  width: 80rpx;
  height: 80rpx;
  border-radius: 60rpx;
}
.avatar-emoji {
  font-size: 44rpx;
}

.user-text {
  display: flex;
  flex-direction: column;
}
.greeting {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--text-primary);
}
.today-date {
  font-size: 24rpx;
  color: var(--text-secondary);
  margin-top: 6rpx;
}

.profile-btn {
  background: rgba(59, 130, 246, 0.12);
  border: none;
  border-radius: 60rpx;
  padding: 12rpx 32rpx;
  font-size: 26rpx;
  color: #3b82f6;
  font-weight: 600;
  backdrop-filter: blur(8rpx);
}
.dark .profile-btn {
  background: rgba(59, 130, 246, 0.25);
  color: #60a5fa;
}
.profile-btn:active {
  transform: scale(0.96);
}

/* 功能卡片网格 - 2列布局 */
.menu-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 28rpx;
}

.menu-card {
  position: relative;
  backdrop-filter: blur(20rpx);
  border-radius: 40rpx;
  padding: 36rpx 16rpx 32rpx;
  text-align: center;
  transition: all 0.3s cubic-bezier(0.2, 0.9, 0.4, 1.2);
  border: 1rpx solid var(--card-border);
  box-shadow: 0 12rpx 32rpx rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

/* 卡片背景色（亮色模式柔和高亮） */
.card-fitness {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(96, 165, 250, 0.25));
}
.card-weightloss {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.18), rgba(56, 189, 248, 0.2));
}
.card-wellness {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.18), rgba(56, 189, 248, 0.2));
}
.card-work {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.2), rgba(20, 184, 166, 0.22));
}
.card-study {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(34, 197, 94, 0.2));
}

/* 暗色模式下卡片背景 */
.dark .card-fitness,
.dark .card-weightloss,
.dark .card-wellness,
.dark .card-work,
.dark .card-study {
  background: rgba(30, 41, 59, 0.7);
  backdrop-filter: blur(20rpx);
  border-color: rgba(255, 255, 255, 0.08);
}

.menu-card .card-glow {
  position: absolute;
  top: -20%;
  left: -20%;
  width: 140%;
  height: 140%;
  background: radial-gradient(circle, rgba(255,255,245,0.3) 0%, rgba(255,255,255,0) 70%);
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}
.menu-card:active {
  transform: scale(0.96);
}
.menu-card:active .card-glow {
  opacity: 0.6;
}

.card-icon-wrapper {
  margin-bottom: 20rpx;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  width: 100rpx;
  height: 100rpx;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 60rpx;
  backdrop-filter: blur(4rpx);
}
.dark .card-icon-wrapper {
  background: rgba(255, 255, 255, 0.1);
}
.card-icon {
  font-size: 64rpx;
}

.card-title {
  font-size: 36rpx;
  font-weight: 800;
  display: block;
  margin-bottom: 12rpx;
  color: var(--text-primary);
}
.card-desc {
  font-size: 22rpx;
  font-weight: 500;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.5);
  display: inline-block;
  padding: 6rpx 20rpx;
  border-radius: 30rpx;
}
.dark .card-desc {
  background: rgba(255, 255, 255, 0.08);
}

/* 健康小贴士 */
.health-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  background: var(--card-bg);
  backdrop-filter: blur(20rpx);
  padding: 26rpx 32rpx;
  border-radius: 48rpx;
  border: 1rpx solid var(--card-border);
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
}
.tip-icon {
  font-size: 36rpx;
}
.tip-text {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  text-align: center;
}
.tip-spark {
  font-size: 28rpx;
  opacity: 0.7;
}

/* 底部氛围光晕 */
.dashboard-ambient {
  position: fixed;
  bottom: -5%;
  left: -20%;
  width: 140%;
  height: 300rpx;
  background: radial-gradient(ellipse, rgba(59, 130, 246, 0.2), transparent 70%);
  border-radius: 50%;
  pointer-events: none;
  z-index: -1;
  filter: blur(60rpx);
}
.dark .dashboard-ambient {
  background: radial-gradient(ellipse, rgba(59, 130, 246, 0.1), transparent 70%);
}
</style>