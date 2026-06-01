<template>
  <view class="register-container">
    <view class="register-card">
      <view class="logo-area">
        <text class="logo-icon">📝</text>
        <text class="logo-title">创建账号</text>
        <text class="logo-sub">加入健康之旅</text>
      </view>

      <input 
        class="input-field" 
        v-model="account" 
        placeholder="账号 / 邮箱" 
        placeholder-class="placeholder"
      />
      <input 
        class="input-field" 
        v-model="password" 
        :password="!showPassword"
        placeholder="密码" 
        placeholder-class="placeholder"
      />
      <input 
        class="input-field" 
        v-model="confirmPwd" 
        :password="!showPassword"
        placeholder="确认密码" 
        placeholder-class="placeholder"
      />
      <view class="pwd-toggle" @click="showPassword = !showPassword">
        <text>{{ showPassword ? '隐藏密码' : '显示密码' }}</text>
      </view>

      <button class="register-btn" @click="handleRegister">立即注册</button>
      <text v-if="errorMsg" class="error">{{ errorMsg }}</text>
      <view class="login-link" @click="goBackToLogin">
        <text>已有账号？去登录</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { useUserStore } from '@/store/user'
import { auth } from '@/utils/api'

const userStore = useUserStore()
const { setUser } = userStore

const account = ref('')
const password = ref('')
const confirmPwd = ref('')
const showPassword = ref(false)
const errorMsg = ref('')

async function handleRegister() {
  errorMsg.value = ''
  if (!account.value.trim() || !password.value.trim()) {
    errorMsg.value = '账号和密码不能为空'
    return
  }
  if (password.value !== confirmPwd.value) {
    errorMsg.value = '两次输入的密码不一致'
    return
  }
  try {
    const res = await auth.register(account.value, password.value)
    setUser(res.token, res.user.account, res.user.nickname || '', res.user.avatar || '')
    uni.showToast({ title: '注册成功', icon: 'success' })
    uni.navigateBack()
  } catch (e) {
    errorMsg.value = e.message
    uni.showToast({ title: e.message, icon: 'none' })
  }
}

function goBackToLogin() {
  uni.navigateTo({ url: '/pages/index/index' })
}
</script>

<style scoped>
.register-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 30rpx 60rpx 60rpx;
  background: radial-gradient(circle at 10% 30%, #eef2ff, #e0e7ff);
}
.register-card {
  width: 100%;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(24px);
  border-radius: 72rpx;
  padding: 40rpx 44rpx 60rpx;
  box-shadow: 0 30rpx 50rpx -20rpx rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.7);
}
.logo-area {
  text-align: center;
  margin-bottom: 40rpx;
}
.logo-icon {
  font-size: 70rpx;
  display: block;
  margin-bottom: 16rpx;
}
.logo-title {
  font-size: 48rpx;
  font-weight: 800;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.logo-sub {
  font-size: 26rpx;
  color: #5b6e8c;
  margin-top: 12rpx;
  display: block;
}
.input-field {
  width: 100%;
  height: 96rpx;
  padding: 0 28rpx;
  margin-bottom: 32rpx;
  background: #f8fafc;
  border-radius: 56rpx;
  border: 1.5px solid #e2e8f0;
  font-size: 32rpx;
  box-sizing: border-box;
  transition: all 0.2s;
}
.input-field:focus {
  border-color: #3b82f6;
  background: white;
  box-shadow: 0 0 0 6rpx rgba(59, 130, 246, 0.1);
}
.pwd-toggle {
  text-align: right;
  margin-top: -16rpx;
  margin-bottom: 40rpx;
  font-size: 26rpx;
  color: #3b82f6;
  padding: 10rpx 20rpx;
  display: inline-block;
}
.register-btn {
  width: 100%;
  height: 96rpx;
  background: linear-gradient(105deg, #2563eb, #1e40af);
  border-radius: 60rpx;
  color: white;
  font-size: 34rpx;
  font-weight: 700;
  border: none;
  box-shadow: 0 12rpx 28rpx -12rpx #1e3a8a;
  margin-bottom: 24rpx;
}
.register-btn:active {
  transform: scale(0.97);
  opacity: 0.9;
}
.error {
  display: block;
  text-align: center;
  color: #ef4444;
  font-size: 26rpx;
  margin: 20rpx 0;
}
.login-link {
  text-align: center;
  margin-top: 24rpx;
  color: #3b82f6;
  font-size: 28rpx;
  font-weight: 500;
  padding: 16rpx;
}
.login-link:active {
  opacity: 0.6;
}
.placeholder {
  color: #94a3b8;
}
</style>