<template>
  <view class="register-page">
    <view class="register-header">
      <text class="logo">DeepTutor</text>
      <text class="subtitle">创建管理员账号</text>
    </view>
    <view class="register-form">
      <u-input v-model="username" placeholder="用户名" prefixIcon="account" border="surround" shape="circle" />
      <u-input v-model="password" placeholder="密码 (至少8位)" type="password" prefixIcon="lock" border="surround" shape="circle" />
      <u-input v-model="confirmPassword" placeholder="确认密码" type="password" prefixIcon="lock" border="surround" shape="circle" />
      <u-button type="primary" shape="circle" :loading="loading" @click="handleRegister">注册</u-button>
      <view class="login-link" @click="goLogin">
        <text>已有账号？去登录</text>
      </view>
    </view>
  </view>
</template>

<script>
import { useUserStore } from '../../store/user'

export default {
  data() {
    return { username: '', password: '', confirmPassword: '', loading: false }
  },
  methods: {
    async handleRegister() {
      if (!this.username || !this.password) {
        uni.showToast({ title: '请填写完整信息', icon: 'none' })
        return
      }
      if (this.password.length < 8) {
        uni.showToast({ title: '密码至少8位', icon: 'none' })
        return
      }
      if (this.password !== this.confirmPassword) {
        uni.showToast({ title: '两次密码不一致', icon: 'none' })
        return
      }
      this.loading = true
      try {
        const userStore = useUserStore()
        await userStore.register(this.username, this.password)
        uni.reLaunch({ url: '/pages/study/deeptutor/index/index' })
      } catch (e) {
        uni.showToast({ title: e.message || '注册失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    goLogin() {
      uni.navigateBack()
    },
  },
}
</script>

<style lang="scss" scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 60rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.register-header {
  text-align: center;
  margin-bottom: 80rpx;
  .logo { display: block; font-size: 56rpx; font-weight: bold; color: #fff; }
  .subtitle { display: block; font-size: 28rpx; color: rgba(255,255,255,0.8); margin-top: 16rpx; }
}
.register-form {
  background: #fff; border-radius: 24rpx; padding: 60rpx 40rpx;
  .u-input { margin-bottom: 30rpx; }
  .u-button { margin-top: 20rpx; }
}
.login-link { text-align: center; margin-top: 30rpx; color: #4f46e5; font-size: 28rpx; }
</style>
