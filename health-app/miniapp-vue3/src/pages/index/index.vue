<template>
  <view class="container">
    <!-- ========= 未登录：显示登录/注册表单 ========= -->
    <view v-if="!isLoggedIn" class="auth-card">
      <!-- 新增 Logo 区域 -->
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

    <!-- ========= 已登录：缤纷卡片仪表板 ========= -->
    <view v-else class="dashboard">
      <!-- 顶部用户栏 -->
      <view class="user-bar">
        <view class="user-info">
          <view class="avatar-ring">
            <text class="avatar-emoji">🧘</text>
          </view>
          <view class="user-text">
            <text class="greeting">🌿 你好，{{ username }}</text>
            <text class="today-date">{{ currentDate }}</text>
          </view>
        </view>
        <button class="logout-btn" @click="logout">退出</button>
      </view>

      <!-- 四色功能卡片网格 -->
      <view class="menu-grid">
        <view class="menu-card card-fitness" @click="goFitness">
          <view class="card-glow"></view>
          <!-- <view class="card-icon-wrapper">
            <text class="card-icon">❤️</text>
          </view> -->
          <text class="card-title">健康</text>
          <text class="card-desc">综合健康管理</text>
        </view>
        <!-- <view class="menu-card card-weightloss" @click="goWeightLoss">
          <view class="card-glow"></view> -->
          <!-- <view class="card-icon-wrapper">
            <text class="card-icon">🥗</text>
          </view> -->
          <!-- <text class="card-title">减肥</text>
          <text class="card-desc">科学减脂计划</text>
        </view>
        <view class="menu-card card-wellness" @click="goWellness">
          <view class="card-glow"></view> -->
          <!-- <view class="card-icon-wrapper">
            <text class="card-icon">🧘</text>
          </view> -->
          <!-- <text class="card-title">养生</text>
          <text class="card-desc">调养身心</text>
        </view> -->
        <view class="menu-card card-work" @click="goWork">
          <view class="card-glow"></view>
          <!-- <view class="card-icon-wrapper">
            <text class="card-icon">💼</text>
          </view> -->
          <text class="card-title">工作</text>
          <text class="card-desc">效率与专注</text>
        </view>
        <view class="menu-card card-study" @click="goStudy">
          <view class="card-glow"></view>
          <!-- <view class="card-icon-wrapper">
            <text class="card-icon">📚</text>
          </view> -->
          <text class="card-title">学习</text>
          <text class="card-desc">学习计划与个人助手</text>
        </view>
      </view>

      <!-- 动态健康小贴士（每天更新不同内容） -->
      <view class="health-tip">
        <text class="tip-icon">🌱</text>
        <text class="tip-text">{{ dailyTip }}</text>
        <text class="tip-spark">✨</text>
      </view>

      <!-- 底部装饰光晕 -->
      <view class="dashboard-ambient"></view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useUserStore } from '@/store/user'
import { auth } from '@/utils/api'

const userStore = useUserStore()
const { isLoggedIn, state, setUser, clearUser } = userStore

// 登录表单
const account = ref('demo')
const password = ref('demo123')
const authError = ref('')
const showPassword = ref(false)

// 用户名（响应式）
const username = computed(() => state.username)

// 当前日期（用于展示）
const currentDate = computed(() => {
  const now = new Date()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekday = weekdays[now.getDay()]
  return `${month}.${day} · ${weekday}`
})

// ---------- 每日健康小贴士库（每天自动轮换） ----------
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
  '步行或骑行代替短途驾车'
]

// 根据当前日期（年积日）选择一条提示，确保每天固定且不同
const dailyTip = computed(() => {
  const today = new Date()
  const startOfYear = new Date(today.getFullYear(), 0, 0)
  const dayOfYear = Math.floor((today - startOfYear) / (24 * 60 * 60 * 1000))
  const index = dayOfYear % tipsList.length
  return '今日微习惯：' + tipsList[index]
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
    uni.showToast({ title: '登录成功', icon: 'success' })
  } catch (e) {
    authError.value = e.message
    uni.showToast({ title: e.message, icon: 'none' })
  }
}

// 注册
async function handleRegister() {
  uni.navigateTo({ url: '/pages/register/register' })
}

// 退出登录
function logout() {
  uni.showModal({
    title: '提示',
    content: '确定要退出登录吗？',
    success: (res) => {
      if (res.confirm) {
        clearUser()
        uni.showToast({ title: '已退出', icon: 'none' })
      }
    }
  })
}

// 功能跳转
function goFitness() {
  uni.navigateTo({ url: '/pages/workout/workout' })
}

function goWeightLoss() {
  uni.navigateTo({ url: '/pages/weightloss/weightloss' })
}

function goWellness() {
  uni.navigateTo({ url: '/pages/wellness/wellness' })
}

function goWork() {
  uni.navigateTo({ url: '/pages/work/work' })
}

function goStudy() {
  uni.navigateTo({ url: '/pages/study/index' })
}
</script>

<style scoped>
.container {
  padding: 32rpx;
  min-height: 100vh;
  background: linear-gradient(180deg, #f3f9ff 0%, #eef5ff 100%);
}

/* ========= 登录表单样式 - 高级毛玻璃（未修改） ========= */
.auth-card {
  margin-top: 80rpx;
  padding: 50rpx 40rpx 60rpx;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  border-radius: 60rpx;
  box-shadow: 0 25rpx 50rpx -12rpx rgba(0, 0, 0, 0.15), 0 0 0 1rpx rgba(255, 255, 255, 0.6) inset;
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
  background: linear-gradient(135deg, #1e293b, #2d3e5f);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: -0.5rpx;
  display: block;
}
.logo-sub {
  font-size: 24rpx;
  color: #5b6e8c;
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
  background: #f8fafc;
  border-radius: 48rpx;
  border: 1.5px solid #e2e8f0;
  box-sizing: border-box;
  transition: all 0.2s;
  color: #1e293b;
}
.auth-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 6rpx rgba(59, 130, 246, 0.15);
  background: #ffffff;
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
  transition: all 0.2s;
}
.toggle-pwd-btn:active {
  background: #d9e6ff;
  transform: translateY(-50%) scale(0.96);
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
  transition: all 0.2s;
}
.auth-btn.primary {
  background: linear-gradient(105deg, #2563eb, #1e40af);
  color: white;
  box-shadow: 0 12rpx 24rpx -10rpx rgba(37, 99, 235, 0.4);
}
.auth-btn.primary:active {
  transform: scale(0.97);
  box-shadow: 0 6rpx 16rpx -8rpx rgba(37, 99, 235, 0.5);
}
.auth-btn.secondary {
  background: rgba(255, 255, 255, 0.9);
  color: #1e293b;
  border: 1px solid #cbd5e1;
}
.auth-btn.secondary:active {
  transform: scale(0.97);
  background: #f1f5f9;
}
.error {
  color: #ef4444;
  font-size: 26rpx;
  margin-top: 24rpx;
  display: block;
  text-align: center;
  font-weight: 500;
}

/* ========= 已登录仪表板 ———— 丰富色彩 ========= */
.dashboard {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 44rpx;
  animation: fadeUp 0.5s cubic-bezier(0.2, 0.9, 0.4, 1.1);
  padding-bottom: 40rpx;
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
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(96, 165, 250, 0.18));
  backdrop-filter: blur(20rpx);
  border-radius: 40rpx;
  padding: 20rpx 24rpx 20rpx 20rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.7);
  box-shadow: 0 22rpx 50rpx rgba(59, 130, 246, 0.12);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.avatar-ring {
  width: 80rpx;
  height: 80rpx;
  background: linear-gradient(135deg, #fff5e6, #ffffff);
  border-radius: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 16rpx -6rpx rgba(0, 0, 0, 0.05), 0 0 0 2rpx rgba(255, 255, 255, 0.8) inset;
}

.avatar-emoji {
  font-size: 44rpx;
  filter: drop-shadow(0 2rpx 4rpx rgba(0, 0, 0, 0.1));
}

.user-text {
  display: flex;
  flex-direction: column;
}

.greeting {
  font-size: 34rpx;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.3rpx;
  line-height: 1.3;
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

.tip-icon {
  font-size: 36rpx;
  filter: drop-shadow(0 2rpx 6rpx rgba(80, 120, 80, 0.2));
}

.tip-text {
  font-size: 26rpx;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: 0.5rpx;
  flex: 1;
  text-align: center;
}

.tip-spark {
  font-size: 28rpx;
  opacity: 0.7;
}

/* 底部环境光晕 */
.dashboard-ambient {
  position: fixed;
  bottom: -10%;
  left: -20%;
  width: 140%;
  height: 240rpx;
  background: radial-gradient(ellipse, rgba(150, 180, 210, 0.3), transparent 70%);
  border-radius: 50%;
  pointer-events: none;
  z-index: -1;
  filter: blur(50rpx);
}
</style>