<template>
  <view class="hub-page" :class="{ dark: isDark }">
    <view class="top-decoration"></view>
    <view class="form-container">
      <view class="header">
        <view class="header-icon-wrapper">
          <text class="header-icon">➕</text>
        </view>
        <text class="header-title">添加记录</text>
        <text class="header-subtitle">选择要添加的记录类型</text>
      </view>

      <view class="hub-grid">
        <view class="hub-card" @click="goTo('/pages/workout/add')">
          <text class="hub-emoji">🏃</text>
          <text class="hub-label">添加运动</text>
          <text class="hub-desc">记录跑步、游泳等运动</text>
        </view>
        <view class="hub-card" @click="goTo('/pages/sleep/add')">
          <text class="hub-emoji">😴</text>
          <text class="hub-label">添加睡眠</text>
          <text class="hub-desc">记录睡眠时长和质量</text>
        </view>
        <view class="hub-card" @click="goTo('/pages/diet/add')">
          <text class="hub-emoji">🍚</text>
          <text class="hub-label">添加饮食</text>
          <text class="hub-desc">记录食物和热量摄入</text>
        </view>
        <view class="hub-card" @click="goTo('/pages/workout/add-water')">
          <text class="hub-emoji">💧</text>
          <text class="hub-label">添加饮水</text>
          <text class="hub-desc">记录今日饮水量</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { useThemeStore } from '@/store/theme'

const themeStore = useThemeStore()
const { isDark } = themeStore

function goTo(url) {
  uni.navigateTo({ url })
}
</script>

<style lang="scss" scoped>
.hub-page {
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  position: relative;
  overflow: hidden;
}

.top-decoration {
  position: absolute;
  top: -120rpx;
  right: -120rpx;
  width: 400rpx;
  height: 400rpx;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.15), rgba(59, 130, 246, 0));
}

.form-container {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 32rpx 80rpx;
}

.header {
  text-align: center;
  margin-bottom: 60rpx;
}

.header-icon-wrapper {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(37, 99, 235, 0.2));
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24rpx;
  box-shadow: 0 16rpx 32rpx rgba(59, 130, 246, 0.2);
}

.header-icon {
  font-size: 52rpx;
}

.header-title {
  display: block;
  font-size: 44rpx;
  font-weight: 700;
  background: linear-gradient(135deg, #1e2b3c, #2c4c6c);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 12rpx;
}

.header-subtitle {
  display: block;
  font-size: 28rpx;
  color: var(--text-tertiary);
}

.hub-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24rpx;
  width: 100%;
  max-width: 650rpx;
}

.hub-card {
  background: var(--card-bg);
  border-radius: 32rpx;
  padding: 36rpx 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.06);
  border: 1rpx solid var(--card-border);
  transition: transform 0.15s;
}

.hub-card:active {
  transform: scale(0.96);
}

.hub-emoji {
  font-size: 64rpx;
  margin-bottom: 16rpx;
}

.hub-label {
  font-size: 30rpx;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8rpx;
}

.hub-desc {
  font-size: 24rpx;
  color: var(--text-tertiary);
}

@media (max-width: 550px) {
  .form-container {
    padding: 40rpx 24rpx 60rpx;
  }
  .header-title {
    font-size: 38rpx;
  }
  .hub-card {
    padding: 28rpx 16rpx;
  }
}
</style>
