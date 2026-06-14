<template>
  <view class="study-container" :class="{ dark: isDark }">
    <view class="hero-card">
      <view class="hero-top-row">
        <view class="hero-copy">
          <text class="hero-title">学习计划</text>
          <text class="hero-subtitle">为你智能推荐的当天任务与个人知识助手入口</text>
        </view>
        <button class="add-plan-btn" @tap="goAddPlan">添加计划</button>
      </view>
      <view class="hero-tags">
        <text class="hero-tag">高效学习</text>
        <text class="hero-tag">每日打卡</text>
        <text class="hero-tag">智能问答</text>
      </view>
    </view>

    <view class="section-header">
      <text class="section-title">今日学习清单</text>
      <text class="section-note">共 {{ plans.length }} 条计划，左右滑动查看更多</text>
      <text v-if="loadError" class="load-error">{{ loadError }}</text>
      <text v-if="isLoading" class="load-info">正在从后端加载计划…</text>
    </view>

    <scroll-view class="plan-scroll" scroll-x="true" show-scrollbar="false">
      <view class="plan-list">
        <view v-for="plan in plans" :key="plan.id" class="plan-card">
          <button class="delete-btn" @click.stop="confirmDelete(plan.id)">✖</button>
          <view class="card-badge">计划 {{ plan.id }}</view>
          <text class="plan-content">{{ plan.content }}</text>
          <view class="plan-time-row">
            <view class="time-block">
              <text class="time-label">开始</text>
              <text class="time-value">{{ formatDisplayTime(plan.startTime) }}</text>
            </view>
            <view class="time-block">
              <text class="time-label">结束</text>
              <text class="time-value">{{ formatDisplayTime(plan.endTime) }}</text>
            </view>
          </view>
          <!-- <view class="plan-footer">
            <button class="assistant-btn" @click="openAssistant(plan)">进入助手</button>
          </view> -->
        </view>
      </view>
    </scroll-view>

    <view class="aidlearning-card">
      <view class="aidlearning-icon">🤖</view>
      <view class="aidlearning-content">
        <text class="aidlearning-title">学习助手</text>
        <text class="aidlearning-desc">进入学习助手，获得个性化学习建议与智能问答支持</text>
      </view>
      <button class="aidlearning-btn" @tap="goAidlearning">进入</button>
    </view>

    <view class="pomodoro-entry-card">
      <view class="pomodoro-entry-icon">🍅</view>
      <view class="pomodoro-entry-content">
        <text class="pomodoro-entry-title">番茄钟</text>
        <text class="pomodoro-entry-desc">进入番茄钟专注计时，提升学习效率</text>
      </view>
      <button class="pomodoro-open-btn" @tap="goPomodoro">打开</button>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { studyApi } from '@/utils/api'
import { useThemeStore } from '@/store/theme'
const themeStore = useThemeStore()
const { isDark } = themeStore

const plans = ref([])
const isLoading = ref(false)
const loadError = ref('')

// 格式化显示时间：ISO字符串 -> "6月7日 09:00"
function formatDisplayTime(isoStr) {
  if (!isoStr) return '--'
  try {
    const date = new Date(isoStr)
    const month = date.getMonth() + 1
    const day = date.getDate()
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${month}月${day}日 ${hours}:${minutes}`
  } catch {
    return isoStr
  }
}

async function loadPlans() {
  isLoading.value = true
  loadError.value = ''
  try {
    const list = await studyApi.list()
    if (Array.isArray(list) && list.length > 0) {
      plans.value = list
    }
  } catch (e) {
    loadError.value = '学习计划获取失败，显示测试数据'
  } finally {
    isLoading.value = false
  }
}

function goAddPlan() {
  uni.navigateTo({
    url: '/pages/study/add',
    success: () => {
      console.log('跳转至添加学习计划页面成功')
    },
    fail: (err) => {
      console.error('跳转失败：', err)
      uni.showToast({ title: '跳转失败，请检查页面路由', icon: 'none' })
    }
  })
}

function openAssistant(plan) {
  const url = `/pages/study/chat?planId=${plan.id}&title=${encodeURIComponent(plan.content)}`
  uni.navigateTo({ url })
}

function goAidlearning() {
  uni.navigateTo({
    url: '/pages/study/aidlearning/index/index',
    success: () => {
      console.log('跳转至学习助手页面成功')
    },
    fail: (err) => {
      console.error('跳转失败：', err)
      uni.showToast({ title: '跳转失败，请检查页面路由', icon: 'none' })
    }
  })
}

function goPomodoro() {
  uni.navigateTo({
    url: '/pages/work/pomodoro',
    fail: (err) => {
      console.error('跳转失败：', err)
      uni.showToast({ title: '跳转失败，请检查页面路由', icon: 'none' })
    }
  })
}

function confirmDelete(id) {
  uni.showModal({
    title: '确认删除',
    content: '确定要删除该学习计划吗？此操作不可恢复。',
    showCancel: true,
    confirmText: '删除',
    cancelText: '取消',
    success: (res) => {
      if (res.confirm) {
        deletePlan(id)
      }
    }
  })
}

async function deletePlan(id) {
  try {
    if (studyApi && typeof studyApi.delete === 'function') {
      await studyApi.delete(id)
    } else if (studyApi && typeof studyApi.remove === 'function') {
      await studyApi.remove(id)
    }
  } catch (e) {
    console.warn('调用后端删除接口失败，进行本地删除', e)
  } finally {
    plans.value = plans.value.filter(p => p.id !== id)
    uni.showToast({ title: '已删除', icon: 'success' })
  }
}

onShow(() => {
  loadPlans()
})
</script>

<style scoped>
.study-container {
  padding: 32rpx;
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
}

.hero-card {
  position: relative;
  padding: 34rpx 30rpx 30rpx;
  border-radius: 40rpx;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(96, 165, 250, 0.18));
  backdrop-filter: blur(20rpx);
  border: 1rpx solid var(--card-border);
  box-shadow: 0 22rpx 50rpx rgba(59, 130, 246, 0.12);
  overflow: hidden;
  margin-bottom: 30rpx;
}

.hero-card::after {
  content: '';
  position: absolute;
  right: -50rpx;
  top: -40rpx;
  width: 180rpx;
  height: 180rpx;
  background: rgba(59, 130, 246, 0.12);
  border-radius: 50%;
  pointer-events: none;
}

.hero-title {
  font-size: 48rpx;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1.1;
}

.hero-subtitle {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.6;
}

.hero-tags {
  position: relative;
  z-index: 1;
  margin-top: 24rpx;
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.hero-top-row {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
}

.hero-copy {
  flex: 1;
  min-width: 0;
}

.add-plan-btn {
  position: relative;
  z-index: 2;
  margin: 0;
  min-width: 180rpx;
  height: 72rpx;
  padding: 0 30rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  border: none;
  border-radius: 999rpx;
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 700;
  line-height: 1;
  box-shadow: 0 16rpx 24rpx rgba(56, 189, 248, 0.22);
  flex-shrink: 0;
}

.hero-tag {
  background: rgba(59, 130, 246, 0.12);
  color: var(--text-primary);
  padding: 12rpx 18rpx;
  border-radius: 26rpx;
  font-size: 24rpx;
  font-weight: 600;
}

.section-header {
  padding: 0 6rpx;
  margin-bottom: 18rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--text-primary);
}

.section-note {
  margin-top: 8rpx;
  font-size: 24rpx;
  color: var(--text-secondary);
}

.load-error {
  margin-top: 14rpx;
  display: block;
  color: #dc2626;
  font-size: 24rpx;
}

.load-info {
  margin-top: 14rpx;
  display: block;
  color: #2563eb;
  font-size: 24rpx;
}

.plan-scroll {
  width: 100%;
}

.plan-list {
  display: flex;
  gap: 22rpx;
  padding-bottom: 18rpx;
}

.plan-card {
  width: 560rpx;
  min-width: 560rpx;
  padding: 30rpx;
  background: var(--card-bg);
  border-radius: 40rpx;
  border: 1rpx solid var(--card-border);
  box-shadow: 0 28rpx 50rpx rgba(15, 23, 42, 0.06);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.delete-btn {
  position: absolute;
  top: 18rpx;
  right: 18rpx;
  width: 64rpx;
  height: 64rpx;
  border-radius: 40rpx;
  border: none;
  background: rgba(0,0,0,0.06);
  color: #9b0000;
  font-size: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.delete-btn:active {
  background: rgba(0,0,0,0.12);
}

.plan-card::before {
  content: '';
  position: absolute;
  right: -60rpx;
  top: -40rpx;
  width: 180rpx;
  height: 180rpx;
  background: rgba(16, 185, 129, 0.12);
  border-radius: 50%;
}

.card-badge {
  align-self: flex-start;
  padding: 12rpx 18rpx;
  border-radius: 999rpx;
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
  font-size: 22rpx;
  font-weight: 700;
  margin-bottom: 18rpx;
}

.plan-content {
  font-size: 34rpx;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1.3;
  margin-bottom: 18rpx;
}

.plan-time-row {
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
  margin-bottom: 24rpx;
}

.time-block {
  flex: 1;
  padding: 18rpx 18rpx 16rpx;
  border-radius: 28rpx;
  background: var(--card-bg);
  border: 1rpx solid var(--input-border);
}

.time-label {
  display: block;
  font-size: 22rpx;
  color: var(--text-secondary);
  margin-bottom: 8rpx;
}

.time-value {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--text-primary);
}

.plan-footer {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.assistant-btn {
  align-self: flex-end;
  min-width: 180rpx;
  background: linear-gradient(90deg, #0ea5e9, #14b8a6);
  color: #ffffff;
  border: none;
  border-radius: 32rpx;
  padding: 16rpx 28rpx;
  font-size: 28rpx;
  font-weight: 700;
  box-shadow: 0 16rpx 26rpx rgba(14, 165, 233, 0.18);
}

.aidlearning-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-top: 30rpx;
  padding: 28rpx 26rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.14), rgba(34, 197, 94, 0.12));
  backdrop-filter: blur(20rpx);
  border-radius: 36rpx;
  border: 1rpx solid var(--card-border);
  box-shadow: 0 20rpx 44rpx rgba(14, 165, 233, 0.14);
}

.aidlearning-icon {
  font-size: 56rpx;
  line-height: 56rpx;
  flex-shrink: 0;
}

.aidlearning-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.aidlearning-title {
  font-size: 32rpx;
  font-weight: 800;
  color: var(--text-primary);
}

.aidlearning-desc {
  font-size: 24rpx;
  color: var(--text-secondary);
  line-height: 1.4;
}

.aidlearning-btn {
  flex-shrink: 0;
  min-width: 120rpx;
  height: 64rpx;
  background: linear-gradient(90deg, #0ea5e9, #14b8a6);
  color: #ffffff;
  border: none;
  border-radius: 32rpx;
  font-size: 26rpx;
  font-weight: 700;
  box-shadow: 0 12rpx 20rpx rgba(14, 165, 233, 0.2);
}

.pomodoro-entry-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-top: 30rpx;
  padding: 28rpx 26rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.14), rgba(34, 197, 94, 0.12));
  backdrop-filter: blur(20rpx);
  border-radius: 36rpx;
  border: 1rpx solid var(--card-border);
  box-shadow: 0 20rpx 44rpx rgba(14, 165, 233, 0.14);
}

.pomodoro-entry-icon {
  font-size: 56rpx;
  line-height: 56rpx;
  flex-shrink: 0;
}

.pomodoro-entry-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.pomodoro-entry-title {
  font-size: 32rpx;
  font-weight: 800;
  color: var(--text-primary);
}

.pomodoro-entry-desc {
  font-size: 24rpx;
  color: var(--text-secondary);
  line-height: 1.4;
}

.pomodoro-open-btn {
  flex-shrink: 0;
  min-width: 120rpx;
  height: 64rpx;
  background: linear-gradient(90deg, #0ea5e9, #14b8a6);
  color: #ffffff;
  border: none;
  border-radius: 32rpx;
  font-size: 26rpx;
  font-weight: 700;
  box-shadow: 0 12rpx 20rpx rgba(14, 165, 233, 0.2);
}
</style>
