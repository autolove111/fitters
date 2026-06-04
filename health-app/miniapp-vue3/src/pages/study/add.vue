<template>
  <view class="add-container" :class="{ dark: isDark }">
    <view class="page-header">
      <text class="page-title">添加学习计划</text>
      <text class="page-note">填写计划内容与时间后，提交到后端保存。</text>
    </view>

    <view class="form-card">
      <view class="field">
        <text class="label">计划内容</text>
        <textarea
          class="textarea"
          v-model="content"
          placeholder="请输入学习内容，例如：阅读第2章理论"
          placeholder-class="placeholder"
          auto-height
          maxlength="200"
        />
      </view>

      <view class="field-row">
        <view class="field small-field">
          <text class="label">开始时间</text>
          <input
            class="input"
            v-model="start"
            placeholder="2026-05-26 09:00"
            placeholder-class="placeholder"
          />
        </view>
        <view class="field small-field">
          <text class="label">结束时间</text>
          <input
            class="input"
            v-model="end"
            placeholder="2026-05-26 10:00"
            placeholder-class="placeholder"
          />
        </view>
      </view>

      <button class="submit-btn" @click="submitPlan">提交学习计划</button>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { studyApi } from '@/utils/api'
import { useThemeStore } from '@/store/theme'
const themeStore = useThemeStore()
const { isDark } = themeStore

const content = ref('')
const start = ref('')
const end = ref('')

async function submitPlan() {
  if (!content.value.trim()) {
    uni.showToast({ title: '请填写计划内容', icon: 'none' })
    return
  }
  if (!start.value.trim() || !end.value.trim()) {
    uni.showToast({ title: '请填写开始和结束时间', icon: 'none' })
    return
  }

  try {
    await studyApi.add({ content: content.value, start: start.value, end: end.value })
    uni.showToast({ title: '学习计划已保存', icon: 'success' })
    uni.navigateBack()
  } catch (err) {
    uni.showToast({ title: err.message || '提交失败，请稍后重试', icon: 'none' })
  }
}
</script>

<style scoped>
.add-container {
  min-height: 100vh;
  padding: 32rpx;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  box-sizing: border-box;
}
.page-header {
  padding: 30rpx 24rpx;
  border-radius: 36rpx;
  background: rgba(59, 130, 246, 0.12);
  margin-bottom: 30rpx;
  box-sizing: border-box;
}
.page-title {
  font-size: 38rpx;
  font-weight: 800;
  color: var(--text-primary);
}
.page-note {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  color: var(--text-secondary);
}
.form-card {
  padding: 30rpx;
  border-radius: 40rpx;
  background: var(--card-bg);
  box-shadow: 0 24rpx 50rpx rgba(15, 23, 42, 0.08);
  box-sizing: border-box;
  width: 100%;
}
.field {
  margin-bottom: 28rpx;
  width: 100%;
  box-sizing: border-box;
}
.field-row {
  display: flex;
  gap: 22rpx;
  width: 100%;
  box-sizing: border-box;
}
.small-field {
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
}
.label {
  font-size: 26rpx;
  color: var(--text-primary);
  margin-bottom: 16rpx;
  display: block;
}
.textarea,
.input {
  width: 100%;
  box-sizing: border-box;
  font-size: 28rpx;
  color: var(--text-primary);
  border: 1rpx solid var(--input-border);
  border-radius: 32rpx;
  background: var(--input-bg);
}
.textarea {
  min-height: 170rpx;
  padding: 24rpx 22rpx;
  line-height: 44rpx;
}
.input {
  height: 104rpx;
  padding: 0 22rpx;
}
.submit-btn {
  width: 100%;
  margin-top: 16rpx;
  padding: 18rpx 0;
  border-radius: 999rpx;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 700;
  box-sizing: border-box;
}
</style>