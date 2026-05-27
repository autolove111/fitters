<template>
  <view class="page">
    <view class="hero">
      <text class="eyebrow">FITTERS</text>
      <text class="title">健康 · 工作 · 学习</text>
      <text class="subtitle">从首页直接进入你需要的模块，学习入口会直接打开 DeepTutor。</text>
      <text class="date">{{ currentDate }}</text>
    </view>

    <view class="card-list">
      <view class="module-card health" @tap="goHealth">
        <text class="module-kicker">Health</text>
        <text class="module-title">健康</text>
        <text class="module-desc">进入健康管理与运动记录。</text>
      </view>

      <view class="module-card work" @tap="goWork">
        <text class="module-kicker">Work</text>
        <text class="module-title">工作</text>
        <text class="module-desc">进入工作效率与专注模块。</text>
      </view>

      <view class="module-card study" @tap="goStudy">
        <text class="module-kicker">Study</text>
        <text class="module-title">学习</text>
        <text class="module-desc">直接进入 DeepTutor 学习前端。</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const currentDate = computed(() => {
  const now = new Date()
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${weekdays[now.getDay()]}`
})

function goHealth() {
  uni.navigateTo({ url: '/pages/workout/workout' })
}

function goWork() {
  uni.navigateTo({ url: '/pages/work/work' })
}

function goStudy() {
  uni.navigateTo({ url: '/pages/study/deeptutor/index/index' })
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 32rpx;
  background:
    radial-gradient(circle at top left, rgba(255, 214, 165, 0.9), transparent 36%),
    radial-gradient(circle at top right, rgba(147, 197, 253, 0.72), transparent 32%),
    linear-gradient(180deg, #f7fbff 0%, #eef4f8 100%);
  box-sizing: border-box;
}

.hero {
  padding: 36rpx 34rpx;
  border-radius: 36rpx;
  background: rgba(255, 255, 255, 0.78);
  border: 1rpx solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 24rpx 50rpx rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(18rpx);
}

.eyebrow {
  display: block;
  font-size: 22rpx;
  font-weight: 700;
  letter-spacing: 6rpx;
  color: #64748b;
}

.title {
  display: block;
  margin-top: 18rpx;
  font-size: 56rpx;
  line-height: 1.15;
  font-weight: 800;
  color: #0f172a;
}

.subtitle {
  display: block;
  margin-top: 16rpx;
  font-size: 28rpx;
  line-height: 1.6;
  color: #475569;
}

.date {
  display: inline-block;
  margin-top: 24rpx;
  padding: 12rpx 22rpx;
  border-radius: 999rpx;
  background: rgba(15, 23, 42, 0.06);
  color: #1e293b;
  font-size: 24rpx;
  font-weight: 600;
}

.card-list {
  margin-top: 30rpx;
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.module-card {
  padding: 36rpx 30rpx;
  border-radius: 34rpx;
  box-shadow: 0 24rpx 40rpx rgba(15, 23, 42, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.78);
  transition: transform 0.2s ease;
}

.module-card:active {
  transform: scale(0.98);
}

.health {
  background: linear-gradient(135deg, rgba(255, 237, 213, 0.96), rgba(254, 215, 170, 0.96));
}

.work {
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.96), rgba(191, 219, 254, 0.96));
}

.study {
  background: linear-gradient(135deg, rgba(220, 252, 231, 0.96), rgba(167, 243, 208, 0.96));
}

.module-kicker {
  display: block;
  font-size: 22rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
  text-transform: uppercase;
  color: rgba(15, 23, 42, 0.58);
}

.module-title {
  display: block;
  margin-top: 10rpx;
  font-size: 46rpx;
  font-weight: 800;
  color: #0f172a;
}

.module-desc {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  line-height: 1.6;
  color: #334155;
}
</style>
