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

    <!-- ========= 已登录：四个功能卡片（两行两列） ========= -->
    <view v-else class="dashboard">
      <view class="user-bar">
        <view class="greeting-box">
          <text class="greeting">你好，{{ username }}</text>
        </view>
        <button class="logout-btn" @click="logout">退出</button>
      </view>

      <view class="menu-grid">
        <view class="menu-card" @click="goFitness">
          <view class="card-icon">💪</view>
          <text class="card-title">健身</text>
          <text class="card-desc">运动·睡眠·饮食</text>
        </view>
        <view class="menu-card" @click="goWeightLoss">
          <view class="card-icon">🥗</view>
          <text class="card-title">减肥</text>
          <text class="card-desc">科学减脂计划</text>
        </view>
        <view class="menu-card" @click="goWellness">
          <view class="card-icon">🧘</view>
          <text class="card-title">养生</text>
          <text class="card-desc">调养身心</text>
        </view>
        <view class="menu-card" @click="goWork">
          <view class="card-icon">💼</view>
          <text class="card-title">工作</text>
          <text class="card-desc">效率与专注</text>
        </view>
      </view>

      <!-- 新增健康小贴士 -->
      <view class="health-tip">
        <text>🌿 今日微习惯：深呼吸三次，感受当下的平静</text>
      </view>
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
  authError.value = ''
  try {
    const res = await auth.register(account.value, password.value)
    setUser(res.token, res.user.account)
    uni.showToast({ title: '注册成功', icon: 'success' })
  } catch (e) {
    authError.value = e.message
    uni.showToast({ title: e.message, icon: 'none' })
  }
}

// 退出登录
function logout() {
  clearUser()
  uni.showToast({ title: '已退出', icon: 'none' })
}

// 功能跳转
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
</script>

<style scoped>
.container {
  padding: 30rpx;
  min-height: 100vh;
  background: radial-gradient(circle at 10% 20%, rgba(220, 240, 255, 0.5), rgba(235, 245, 255, 0.9));
}

/* ========= 登录表单样式 - 高级毛玻璃 ========= */
.auth-card {
  margin-top: 80rpx;
  padding: 50rpx 40rpx 60rpx;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  border-radius: 60rpx;
  box-shadow: 0 25rpx 50rpx -12rpx rgba(0, 0, 0, 0.15), 0 0 0 1rpx rgba(255, 255, 255, 0.6) inset;
}

/* Logo 区域 */
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

/* ========= 已登录仪表板样式 ========= */
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 40rpx;
  animation: fadeUp 0.4s ease;
}
@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(20rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.user-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.greeting-box {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12rpx);
  padding: 12rpx 32rpx;
  border-radius: 60rpx;
  border: 0.5px solid rgba(255, 255, 245, 0.8);
}
.greeting {
  font-size: 36rpx;
  font-weight: 700;
  background: linear-gradient(125deg, #0f2b3d, #1f4a6e);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: -0.3rpx;
}
.logout-btn {
  background: rgba(248, 113, 113, 0.9);
  backdrop-filter: blur(8rpx);
  border: none;
  border-radius: 60rpx;
  padding: 12rpx 32rpx;
  font-size: 28rpx;
  color: white;
  font-weight: 600;
  transition: all 0.2s;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
}
.logout-btn:active {
  transform: scale(0.96);
  background: #ef4444;
}

/* 两行两列卡片网格 - 高级毛玻璃 */
.menu-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 30rpx;
  padding: 10rpx 0;
}

.menu-card {
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(20rpx);
  border-radius: 52rpx;
  padding: 56rpx 24rpx 44rpx;
  text-align: center;
  transition: all 0.3s cubic-bezier(0.2, 0.9, 0.4, 1.1);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: 0 12rpx 32rpx rgba(0, 0, 0, 0.04);
}

.menu-card:active {
  transform: scale(0.96);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 20rpx 36rpx -12rpx rgba(0, 0, 0, 0.12);
}

.card-icon {
  font-size: 100rpx;
  margin-bottom: 28rpx;
  display: inline-block;
  filter: drop-shadow(0 8rpx 12rpx rgba(0, 0, 0, 0.05));
}

.card-title {
  font-size: 44rpx;
  font-weight: 800;
  background: linear-gradient(135deg, #1e293b, #2c3e50);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  display: block;
  margin-bottom: 16rpx;
  letter-spacing: -0.5rpx;
}

.card-desc {
  font-size: 26rpx;
  font-weight: 500;
  color: #5b6e8c;
  background: rgba(255, 255, 245, 0.7);
  display: inline-block;
  padding: 8rpx 20rpx;
  border-radius: 60rpx;
  backdrop-filter: blur(4rpx);
}

/* 健康小贴士 */
.health-tip {
  margin-top: 20rpx;
  text-align: center;
  font-size: 26rpx;
  color: #5b6e8c;
  background: rgba(255, 255, 245, 0.6);
  padding: 20rpx 24rpx;
  border-radius: 60rpx;
  backdrop-filter: blur(12rpx);
  font-weight: 500;
  letter-spacing: 1rpx;
}

/* 不同卡片图标微投影 */
.menu-card:nth-child(1) .card-icon { text-shadow: 0 4rpx 12rpx rgba(239, 68, 68, 0.2); }
.menu-card:nth-child(2) .card-icon { text-shadow: 0 4rpx 12rpx rgba(16, 185, 129, 0.2); }
.menu-card:nth-child(3) .card-icon { text-shadow: 0 4rpx 12rpx rgba(139, 92, 246, 0.2); }
.menu-card:nth-child(4) .card-icon { text-shadow: 0 4rpx 12rpx rgba(245, 158, 11, 0.2); }
</style>           