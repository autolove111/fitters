<template>
  <view class="container" :class="{ 'dark-bg': !isLoggedIn }">
    <!-- ========= 全新高级登录界面（深色奢华） ========= -->
    <view v-if="!isLoggedIn" class="auth-wrapper">
      <view class="auth-card">
        <view class="brand">
          <text class="brand-symbol">✦</text>
          <text class="brand-name">Fitters</text>
          <view class="brand-divider"></view>
          <text class="brand-sub">health concierge</text>
          <text class="brand-tagline">极致·平衡·生命力</text>
        </view>

        <view class="input-section">
          <view class="input-group">
            <text class="input-label">账号</text>
            <input 
              class="input-field" 
              v-model="account" 
              placeholder="邮箱 / 手机号"
              placeholder-class="input-placeholder"
            />
            <view class="input-line"></view>
          </view>
          <view class="input-group">
            <text class="input-label">密码</text>
            <view class="password-area">
              <input 
                class="input-field" 
                v-model="password" 
                :password="!showPassword"
                placeholder="········"
                placeholder-class="input-placeholder"
              />
              <text class="toggle-pwd" @click="togglePasswordVisibility">
                {{ showPassword ? '隐藏' : '显示' }}
              </text>
            </view>
            <view class="input-line"></view>
          </view>
        </view>

        <view class="forgot-link">
          <text class="forgot-text">忘记密码？</text>
        </view>

        <view class="button-group">
          <button class="btn-login" @click="handleLogin">登录</button>
          <button class="btn-register" @click="handleRegister">注册账号</button>
        </view>

        <text v-if="authError" class="error-text">{{ authError }}</text>
      </view>

      <!-- 装饰光晕 -->
      <view class="ambient-glow"></view>
      <view class="particle particle-1"></view>
      <view class="particle particle-2"></view>
    </view>

    <!-- ========= 已登录仪表板（明亮高级版，保持原有风格） ========= -->
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
        <button class="logout-btn" @click="goProfile">个人中心</button>
      </view>

      <!-- 四色功能卡片网格 -->
      <view class="menu-grid">
        <view class="menu-card card-fitness" @click="goFitness">
          <view class="card-glow"></view>
          <view class="card-icon-wrapper">
            <text class="card-icon">💪</text>
          </view>
          <text class="card-title">健身</text>
          <text class="card-desc">运动·睡眠·饮食</text>
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
      </view>

      <view class="dashboard-atmosphere"></view>
      <view class="floating-dots"></view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/store/user'
import { auth } from '@/utils/api'

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

// 用户名
const username = computed(() => state.username || '探索者')

// 动态问候
const greetingWord = computed(() => {
  const hour = new Date().getHours()
  if (hour < 5) return '🌙 夜深人静'
  if (hour < 9) return '🌅 晨光熹微'
  if (hour < 12) return '☀️ 精神饱满'
  if (hour < 14) return '🍃 午后小憩'
  if (hour < 18) return '⛅ 悠然午后'
  if (hour < 22) return '🌇 暮色温柔'
  return '🌌 静夜沉思'
})

// 当前日期
const currentDate = computed(() => {
  const now = new Date()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekday = weekdays[now.getDay()]
  return `${month}.${day} · ${weekday}`
})

// 卡片配置
const cards = ref([
  { id: 'fitness', title: '健身', sub: '运动 · 睡眠 · 饮食', icon: '💪', route: '/pages/workout/workout' },
  { id: 'weightloss', title: '减脂', sub: '科学计划 · 代谢管理', icon: '🥗', route: '/pages/weightloss/weightloss' },
  { id: 'wellness', title: '养生', sub: '调养 · 呼吸 · 心境', icon: '🧘', route: '/pages/wellness/wellness' },
  { id: 'work', title: '工作', sub: '专注 · 效率 · 心流', icon: '💼', route: '/pages/work/work' }
])

// 每日提示库
const tipLibrary = [
  '静坐十分钟，让思绪沉淀。', '喝一杯温水，唤醒代谢。', '伸展肩颈，释放僵硬。', '闭目养神，归还视觉清澈。',
  '整理一个角落，即整理心绪。', '细嚼慢咽，感恩食物本源。', '站立办公一刻，打断久坐。', '对镜微笑，是面部瑜伽。',
  '写下今日一愿，种下心锚。', '远眺绿植，舒缓眼压。', '睡前冥想，与梦和解。', '真诚赞美一人，流动善意。',
  '深呼吸三次，重置状态。', '步行一段路，感受风拂。', '记录一件小确幸。', '关掉通知一小时。'
]

const dailyTip = computed(() => {
  const today = new Date()
  const dayNum = Math.floor((today - new Date(today.getFullYear(), 0, 0)) / 86400000)
  return tipLibrary[dayNum % tipLibrary.length]
})

// 模拟今日习惯完成率
const habitProgress = computed(() => {
  const today = new Date()
  const seed = today.getFullYear() * 365 + today.getMonth() * 30 + today.getDate()
  return 55 + (seed % 38)
})

// 方法
function togglePasswordVisibility() {
  showPassword.value = !showPassword.value
}

async function handleLogin() {
  authError.value = ''
  try {
    const res = await auth.login(account.value, password.value)
    setUser(res.token, res.user.account)
    uni.showToast({ title: '登录成功', icon: 'success' })
  } catch (e) {
    authError.value = e.message
    uni.showToast({ title: e.message, icon: 'none' })
  }
}

function handleRegister() {
  uni.navigateTo({ url: '/pages/register/register' })
}

// 个人中心
function goProfile() {
  uni.navigateTo({ url: '/pages/profile/index' })
}

function goTo(url) {
  uni.navigateTo({ url })
}

function goStudy() {
  uni.navigateTo({ url: '/pages/study/index' })
}
</script>

<style scoped>
/* 全局容器 — 背景动态切换 */
.container {
  padding: 32rpx;
  min-height: 100vh;
  background: linear-gradient(180deg, #f3f9ff 0%, #eef5ff 100%);
}

/* ========= 登录界面样式（深色奢华） ========= */
.auth-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 32rpx;
  position: relative;
}
.auth-card {
  width: 100%;
  max-width: 600rpx;
  margin: 0 auto;
  padding: 80rpx 56rpx 96rpx;
  background: rgba(25, 35, 45, 0.68);
  backdrop-filter: blur(48rpx);
  border-radius: 128rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 32rpx 80rpx -32rpx rgba(0, 0, 0, 0.5), 0 1rpx 0 0 rgba(255, 255, 255, 0.08) inset;
  animation: cardFloat 0.8s ease-out;
}
@keyframes cardFloat {
  0% { opacity: 0; transform: scale(0.96) translateY(40rpx); }
  100% { opacity: 1; transform: scale(1) translateY(0); }
}
.brand {
  text-align: center;
  margin-bottom: 88rpx;
}
.brand-symbol {
  font-size: 64rpx;
  color: rgba(220, 230, 245, 0.9);
  letter-spacing: 8rpx;
  display: block;
  margin-bottom: 24rpx;
  font-weight: 300;
}
.brand-name {
  font-size: 56rpx;
  font-weight: 300;
  letter-spacing: -1rpx;
  color: #f0f3f8;
  display: block;
  margin-bottom: 20rpx;
  text-transform: lowercase;
}
.brand-divider {
  width: 80rpx;
  height: 1rpx;
  background: rgba(200, 210, 230, 0.4);
  margin: 24rpx auto 20rpx;
}
.brand-sub {
  font-size: 22rpx;
  font-weight: 400;
  letter-spacing: 3rpx;
  color: #a0b3c9;
  text-transform: uppercase;
  display: block;
  margin-bottom: 16rpx;
}
.brand-tagline {
  font-size: 24rpx;
  font-weight: 300;
  color: #7e95ae;
  letter-spacing: 2rpx;
}
.input-section {
  margin-bottom: 48rpx;
}
.input-group {
  margin-bottom: 56rpx;
  position: relative;
}
.input-label {
  font-size: 22rpx;
  font-weight: 500;
  letter-spacing: 2rpx;
  color: #b8cadf;
  margin-bottom: 20rpx;
  display: block;
  text-transform: uppercase;
}
.input-field {
  width: 100%;
  height: 80rpx;
  font-size: 36rpx;
  font-weight: 400;
  color: #f0f4fa;
  background: transparent;
  border: none;
  padding: 0;
  outline: none;
}
.input-placeholder {
  color: #5a7288;
  font-weight: 300;
}
.input-line {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 1rpx;
  background: rgba(150, 180, 210, 0.4);
  transition: all 0.3s ease;
}
.input-field:focus + .input-line {
  background: #c0d4f0;
  height: 2rpx;
  box-shadow: 0 0 12rpx rgba(192, 212, 240, 0.6);
}
.password-area {
  position: relative;
}
.toggle-pwd {
  position: absolute;
  right: 0;
  top: 28rpx;
  font-size: 24rpx;
  font-weight: 500;
  letter-spacing: 1rpx;
  color: #9bb3cc;
  background: rgba(255, 255, 255, 0.05);
  padding: 8rpx 20rpx;
  border-radius: 60rpx;
  backdrop-filter: blur(8rpx);
}
.toggle-pwd:active {
  background: rgba(255, 255, 255, 0.15);
  transform: scale(0.96);
}
.forgot-link {
  text-align: right;
  margin-top: -20rpx;
  margin-bottom: 56rpx;
}
.forgot-text {
  font-size: 24rpx;
  color: #8ba0b8;
  font-weight: 400;
  letter-spacing: 0.5rpx;
  border-bottom: 1rpx dashed rgba(139, 160, 184, 0.5);
}
.button-group {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
}
.btn-login, .btn-register {
  height: 104rpx;
  line-height: 104rpx;
  border-radius: 120rpx;
  font-size: 32rpx;
  font-weight: 500;
  border: none;
  transition: all 0.25s;
}
.btn-login {
  background: linear-gradient(105deg, #e8edf5, #d0dbe8);
  color: #1a2a3a;
  box-shadow: 0 8rpx 24rpx -8rpx rgba(0, 0, 0, 0.3);
}
.btn-login:active {
  transform: scale(0.97);
  background: linear-gradient(105deg, #dce3ed, #c5d1df);
}
.btn-register {
  background: rgba(30, 40, 50, 0.6);
  backdrop-filter: blur(12rpx);
  border: 1rpx solid rgba(255, 255, 255, 0.2);
  color: #d0dfef;
}
.btn-register:active {
  transform: scale(0.97);
  background: rgba(30, 40, 50, 0.8);
}
.error-text {
  text-align: center;
  font-size: 24rpx;
  color: #f0a0a0;
  margin-top: 48rpx;
  font-weight: 400;
  letter-spacing: 0.5rpx;
}
.ambient-glow {
  position: fixed;
  top: -30%;
  left: -20%;
  width: 140%;
  height: 80%;
  background: radial-gradient(ellipse, rgba(70, 130, 200, 0.15), transparent);
  filter: blur(100rpx);
  pointer-events: none;
  z-index: -1;
}
.particle {
  position: fixed;
  width: 500rpx;
  height: 500rpx;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(140, 180, 220, 0.1), transparent);
  filter: blur(80rpx);
  pointer-events: none;
  z-index: -1;
}
.particle-1 {
  bottom: -20%;
  right: -20%;
}
.particle-2 {
  top: -10%;
  left: -10%;
  width: 600rpx;
  height: 600rpx;
  background: radial-gradient(circle, rgba(200, 170, 220, 0.08), transparent);
}

/* ========= 仪表板样式（明亮高级版，与之前一致） ========= */
.dashboard {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 52rpx;
  padding: 32rpx 32rpx 80rpx;
  background: #f0f2f5;
  background-image: radial-gradient(circle at 20% 30%, rgba(215, 225, 240, 0.6) 0%, #eef2f8 100%);
  animation: ascend 0.7s cubic-bezier(0.2, 0.9, 0.3, 1.1);
}
@keyframes ascend {
  from { opacity: 0; transform: translateY(60rpx); }
  to { opacity: 1; transform: translateY(0); }
}
.hero-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(96, 165, 250, 0.18));
  backdrop-filter: blur(20rpx);
  border-radius: 40rpx;
  padding: 20rpx 24rpx 20rpx 20rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.7);
  box-shadow: 0 22rpx 50rpx rgba(59, 130, 246, 0.12);
}
.user-greeting {
  display: flex;
  align-items: center;
  gap: 28rpx;
}
.greeting-avatar {
  position: relative;
  width: 100rpx;
  height: 100rpx;
  background: linear-gradient(145deg, #ffffff, #eef2f6);
  border-radius: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 16rpx -6rpx rgba(0, 0, 0, 0.05), 0 0 0 2rpx rgba(255, 255, 255, 0.8) inset;
  overflow: hidden;
}
.avatar-img {
  width: 80rpx;
  height: 80rpx;
  border-radius: 60rpx;
}
.avatar-glyph {
  font-size: 52rpx;
  opacity: 0.75;
}
.avatar-ring-pulse {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 60rpx;
  border: 2rpx solid rgba(100,140,180,0.4);
  animation: pulseRing 2s infinite;
  pointer-events: none;
}
@keyframes pulseRing {
  0% { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(1.3); opacity: 0; }
}
.greeting-texts {
  display: flex;
  flex-direction: column;
}

.greeting {
  font-size: 34rpx;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.3rpx;
  margin-bottom: 8rpx;
}

.today-date {
  font-size: 24rpx;
  color: #64748b;
  font-weight: 500;
  letter-spacing: 1rpx;
  margin-top: 6rpx;
}

.logout-btn {
  background: rgba(59, 130, 246, 0.12);
  backdrop-filter: blur(12rpx);
  border: none;
  border-radius: 999rpx;
  padding: 12rpx 32rpx;
  font-size: 26rpx;
  color: #2563eb;
  font-weight: 600;
  transition: all 0.2s ease;
  border: 1rpx solid rgba(255, 255, 255, 0.7);
}
.logout-btn:active {
  transform: scale(0.96);
  background: rgba(59, 130, 246, 0.2);
}

/* 功能卡片网格 */
.menu-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 32rpx;
  margin: 8rpx 0;
}

.menu-card {
  position: relative;
  backdrop-filter: blur(20rpx);
  border-radius: 40rpx;
  padding: 48rpx 20rpx 40rpx;
  text-align: center;
  transition: all 0.35s cubic-bezier(0.2, 0.9, 0.4, 1.2);
  border: 1rpx solid rgba(255, 255, 255, 0.7);
  box-shadow: 0 22rpx 50rpx rgba(59, 130, 246, 0.12);
  overflow: hidden;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(229, 242, 255, 0.98));
}

.card-fitness {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(96, 165, 250, 0.18));
}
.card-weightloss {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.16), rgba(56, 189, 248, 0.18));
}
.card-wellness {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.16), rgba(56, 189, 248, 0.18));
}
.card-work {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.16), rgba(20, 184, 166, 0.18));
}
.card-study {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(34, 197, 94, 0.18));
}

.menu-card .card-glow {
  position: absolute;
  top: -20%;
  left: -20%;
  width: 140%;
  height: 140%;
  background: radial-gradient(circle, rgba(255,255,245,0.4) 0%, rgba(255,255,255,0) 70%);
  opacity: 0;
  transition: opacity 0.4s ease;
  pointer-events: none;
  border-radius: 50%;
}

.menu-card:active {
  transform: scale(0.96);
  box-shadow: 0 28rpx 50rpx rgba(59, 130, 246, 0.18);
}
.menu-card:active .card-glow {
  opacity: 0.5;
}

.card-icon-wrapper {
  margin-bottom: 28rpx;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  width: 120rpx;
  height: 120rpx;
  background: rgba(255, 255, 255, 0.55);
  border-radius: 80rpx;
  backdrop-filter: blur(4rpx);
  transition: transform 0.2s ease;
}
.menu-card:active .card-icon-wrapper {
  transform: scale(0.94);
}

.card-icon {
  font-size: 80rpx;
  filter: drop-shadow(0 8rpx 14rpx rgba(0, 0, 0, 0.1));
}

.card-title {
  font-size: 40rpx;
  font-weight: 800;
  display: block;
  margin-bottom: 12rpx;
  letter-spacing: -0.3rpx;
  color: #0f172a;
}

.card-fitness .card-title {
  color: #0f172a;
}
.card-weightloss .card-title {
  color: #0f172a;
}
.card-wellness .card-title {
  color: #0f172a;
}
.card-work .card-title {
  color: #0f172a;
}

.card-desc {
  font-size: 24rpx;
  font-weight: 600;
  color: #475569;
  background: rgba(255, 255, 255, 0.65);
  display: inline-block;
  padding: 8rpx 22rpx;
  border-radius: 26rpx;
  backdrop-filter: blur(4rpx);
}

/* 健康小贴士 - 学习页面风格 */
.health-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  margin-top: 10rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.14), rgba(34, 197, 94, 0.12));
  backdrop-filter: blur(20rpx);
  padding: 26rpx 32rpx;
  border-radius: 36rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.7);
  box-shadow: 0 20rpx 44rpx rgba(14, 165, 233, 0.14);
  transition: all 0.2s;
}
.settings-touch:active {
  background: rgba(0,0,0,0.06);
  transform: rotate(15deg);
}

.tip-text {
  font-size: 26rpx;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: 0.5rpx;
  flex: 1;
  text-align: center;
  transition: all 0.4s cubic-bezier(0.2, 0.9, 0.4, 1.2);
  border: 1rpx solid rgba(255,255,255,0.7);
  box-shadow: 0 24rpx 40rpx -24rpx rgba(0, 0, 0, 0.12);
  overflow: hidden;
}
.card-lift {
  transform: translateY(-12rpx);
  background: rgba(255,255,250,0.9);
  box-shadow: 0 40rpx 60rpx -28rpx rgba(0, 0, 0, 0.25);
}
.card-theme-fitness { background: linear-gradient(135deg, rgba(255,220,180,0.85), rgba(255,200,150,0.7)); }
.card-theme-weightloss { background: linear-gradient(135deg, rgba(190,225,175,0.85), rgba(170,210,150,0.7)); }
.card-theme-wellness { background: linear-gradient(135deg, rgba(215,195,245,0.85), rgba(195,175,235,0.7)); }
.card-theme-work { background: linear-gradient(135deg, rgba(185,210,250,0.85), rgba(165,190,240,0.7)); }
.card-icon-box {
  position: relative;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 28rpx;
}
.card-icon-main {
  font-size: 84rpx;
  z-index: 2;
  filter: drop-shadow(0 8rpx 12rpx rgba(0,0,0,0.1));
}
.icon-bg-blur {
  position: absolute;
  width: 120rpx;
  height: 120rpx;
  background: rgba(255,255,245,0.5);
  border-radius: 80rpx;
  backdrop-filter: blur(6rpx);
  z-index: 0;
}
.card-name {
  font-size: 46rpx;
  font-weight: 680;
  letter-spacing: -0.5rpx;
  display: block;
  margin-bottom: 14rpx;
}
.card-theme-fitness .card-name { color: #c2410c; }
.card-theme-weightloss .card-name { color: #15803d; }
.card-theme-wellness .card-name { color: #6b21a5; }
.card-theme-work .card-name { color: #1e40af; }
.card-sub {
  font-size: 24rpx;
  font-weight: 480;
  color: #38546a;
  background: rgba(250,250,235,0.6);
  padding: 10rpx 26rpx;
  border-radius: 60rpx;
  display: inline-block;
  backdrop-filter: blur(2rpx);
}
.card-decoration {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 6rpx;
  background: linear-gradient(90deg, transparent, rgba(255,255,245,0.8), transparent);
}
.card-inner-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 20% 20%, rgba(255,250,210,0.4), transparent 70%);
  opacity: 0;
  transition: opacity 0.4s;
}
.func-card:active .card-inner-glow {
  opacity: 0.7;
}
.insight-card {
  background: rgba(240, 245, 240, 0.65);
  backdrop-filter: blur(28rpx);
  border-radius: 80rpx;
  padding: 36rpx 32rpx;
  border: 1rpx solid rgba(255,255,245,0.7);
  box-shadow: 0 18rpx 32rpx -20rpx rgba(0,0,0,0.1);
}
.insight-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 28rpx;
  padding: 0 12rpx;
}
.insight-label {
  font-size: 32rpx;
  font-weight: 600;
  color: #2c5a48;
  letter-spacing: 1rpx;
}
.insight-meta {
  font-size: 22rpx;
  font-weight: 500;
  color: #98aa9e;
  letter-spacing: 1.5rpx;
}
.insight-content {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 36rpx;
}
.insight-quote {
  font-size: 64rpx;
  font-family: Georgia, serif;
  color: #bdc9d0;
  line-height: 1;
}
.insight-quote.right {
  align-self: flex-end;
}
.insight-text {
  font-size: 30rpx;
  font-weight: 500;
  color: #2c4b3a;
  flex: 1;
  text-align: center;
  letter-spacing: 0.3rpx;
}
.insight-progress {
  height: 8rpx;
  background: #dbe5e0;
  border-radius: 8rpx;
  margin: 8rpx 12rpx 20rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4a8c6f, #6fb48c);
  border-radius: 8rpx;
  width: 0%;
  transition: width 0.6s ease;
}
.insight-footer {
  font-size: 22rpx;
  color: #7c998b;
  text-align: center;
  margin-top: 16rpx;
}
.dashboard-atmosphere {
  position: fixed;
  bottom: -5%;
  left: -15%;
  width: 130%;
  height: 360rpx;
  background: radial-gradient(ellipse, rgba(140,170,200,0.2), transparent);
  filter: blur(80rpx);
  pointer-events: none;
  z-index: -1;
}
.floating-dots {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: radial-gradient(circle at 30% 40%, rgba(100,120,140,0.08) 2rpx, transparent 2rpx);
  background-size: 48rpx 48rpx;
  pointer-events: none;
  z-index: 0;
  opacity: 0.5;
}
</style>