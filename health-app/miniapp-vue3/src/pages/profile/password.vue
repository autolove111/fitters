<template>
  <view class="password-page" :class="{ dark: isDark }">
    <view class="password-card">
      <text class="card-title">修改密码</text>

      <text class="input-label">旧密码</text>
      <input class="input-field" v-model="oldPassword" type="password" placeholder="请输入旧密码" />

      <text class="input-label">新密码</text>
      <input class="input-field" v-model="newPassword" type="password" placeholder="请输入新密码" />

      <text class="input-label">确认新密码</text>
      <input class="input-field" v-model="confirmPassword" type="password" placeholder="请再次输入新密码" />

      <button class="submit-btn" @click="handleSubmit">确认修改</button>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { useThemeStore } from '@/store/theme'
import { userApi } from '@/utils/api'

const themeStore = useThemeStore()
const { isDark } = themeStore

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

const handleSubmit = async () => {
  if (!oldPassword.value) {
    uni.showToast({ title: '请输入旧密码', icon: 'none' })
    return
  }
  if (!newPassword.value) {
    uni.showToast({ title: '请输入新密码', icon: 'none' })
    return
  }
  if (newPassword.value.length < 6) {
    uni.showToast({ title: '新密码至少6位', icon: 'none' })
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    uni.showToast({ title: '两次输入的密码不一致', icon: 'none' })
    return
  }
  try {
    await userApi.changePassword({
      oldPassword: oldPassword.value,
      newPassword: newPassword.value
    })
    uni.showToast({ title: '密码已修改', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 1500)
  } catch (e) {
    uni.showToast({ title: e.message || '修改失败', icon: 'none' })
  }
}
</script>

<style scoped>
.password-page {
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  padding: 32rpx;
}
.password-card {
  background: var(--card-bg);
  border-radius: 36rpx;
  padding: 40rpx 30rpx;
  border: 1rpx solid var(--card-border);
  box-shadow: 0 20rpx 44rpx rgba(14, 165, 233, 0.1);
}
.card-title {
  font-size: 36rpx;
  font-weight: 700;
  color: var(--text-primary);
  display: block;
  text-align: center;
  margin-bottom: 40rpx;
}
.input-label {
  font-size: 26rpx;
  color: var(--text-secondary);
  display: block;
  margin-bottom: 12rpx;
  margin-top: 24rpx;
}
.input-field {
  height: 88rpx;
  border: 1rpx solid var(--input-border);
  border-radius: 24rpx;
  padding: 0 24rpx;
  font-size: 30rpx;
  background: var(--input-bg);
}
.submit-btn {
  width: 100%;
  height: 88rpx;
  border-radius: 999rpx;
  border: none;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 700;
  margin-top: 50rpx;
  box-shadow: 0 16rpx 32rpx rgba(56, 189, 248, 0.22);
}
</style>
