<template>
  <view class="login-page">
    <view class="login-header">
      <text class="logo">AidLearning</text>
      <text class="subtitle">AI 智能学习助手</text>
    </view>
    <view class="login-form">
      <u-input v-model="username" placeholder="用户名" prefixIcon="account" border="surround" shape="circle" />
      <u-input v-model="password" placeholder="密码" type="password" prefixIcon="lock" border="surround" shape="circle" />
      <u-button type="primary" shape="circle" :loading="loading" @click="handleLogin">登录</u-button>
      <view class="register-link" @click="goRegister">
        <text>还没有账号？立即注册</text>
      </view>
    </view>
  </view>
</template>

<script>
import { useUserStore } from '../../store/user'

export default {
  data() {
    return { username: '', password: '', loading: false }
  },
  methods: {
    async handleLogin() {
      if (!this.username || !this.password) {
        uni.showToast({ title: '请输入用户名和密码', icon: 'none' })
        return
      }
      this.loading = true
      try {
        const userStore = useUserStore()
        await userStore.login(this.username, this.password)
        uni.reLaunch({ url: '/pages/study/aidlearning/index/index' })
      } catch (e) {
        uni.showToast({ title: e.message || '登录失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    goRegister() {
      uni.navigateTo({ url: '/pages/study/aidlearning/register/register' })
    },
  },
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 60rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-header {
  text-align: center;
  margin-bottom: 80rpx;
  .logo {
    display: block;
    font-size: 56rpx;
    font-weight: bold;
    color: #fff;
  }
  .subtitle {
    display: block;
    font-size: 28rpx;
    color: rgba(255, 255, 255, 0.8);
    margin-top: 16rpx;
  }
}
.login-form {
  background: #fff;
  border-radius: 24rpx;
  padding: 60rpx 40rpx;
  .u-input {
    margin-bottom: 30rpx;
  }
  .u-button {
    margin-top: 20rpx;
  }
}
.register-link {
  text-align: center;
  margin-top: 30rpx;
  color: #4f46e5;
  font-size: 28rpx;
}
</style>
