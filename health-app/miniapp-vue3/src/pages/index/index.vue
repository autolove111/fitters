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
        <view class="toggle-pwd-btn" @click="togglePasswordVisibility">
          <text>{{ showPassword ? '隐藏密码' : '显示密码' }}</text>
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
        <text class="greeting">你好，{{ username }}</text>
        <button class="logout-btn" @click="logout">退出登录</button>
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
  background-color: #f5f7fa;
  min-height: 100vh;
}

/* 登录表单样式 */
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
  padding-right: 160rpx;
  margin-bottom: 0;
}
.toggle-pwd-btn {
  position: absolute;
  right: 20rpx;
  top: 50%;
  transform: translateY(-50%);
  background-color: #f0f2f5;
  padding: 8rpx 20rpx;
  border-radius: 48rpx;
  font-size: 26rpx;
  color: #409eff;
  font-weight: 500;
  transition: all 0.2s;
}
.toggle-pwd-btn:active {
  background-color: #e4e7ed;
  transform: translateY(-50%) scale(0.96);
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

/* 已登录：功能菜单（两行两列） */
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 40rpx;
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

/* 两行两列卡片网格 */
.menu-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 30rpx;
  padding: 20rpx 0;
}

.menu-card {
  background: white;
  border-radius: 40rpx;
  padding: 50rpx 20rpx 40rpx;
  text-align: center;
  box-shadow: 0 12rpx 32rpx rgba(0, 0, 0, 0.08);
  transition: all 0.25s ease;
  border: 1px solid rgba(255,255,255,0.3);
}

.menu-card:active {
  transform: scale(0.96);
  box-shadow: 0 6rpx 16rpx rgba(0, 0, 0, 0.1);
}

.card-icon {
  font-size: 96rpx;
  margin-bottom: 24rpx;
  display: inline-block;
}

.card-title {
  font-size: 40rpx;
  font-weight: 700;
  color: #2c3e50;
  display: block;
  margin-bottom: 12rpx;
  letter-spacing: 2rpx;
}

.card-desc {
  font-size: 26rpx;
  color: #7f8c8d;
  display: block;
  line-height: 1.4;
}
</style>