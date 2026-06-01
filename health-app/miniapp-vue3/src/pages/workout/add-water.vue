<template>
  <view class="form-page" :class="{ dark: isDark }">
    <view class="top-decoration"></view>
    <view class="form-container">
      <view class="header">
        <view class="header-icon-wrapper">
          <text class="header-icon">💧</text>
        </view>
        <text class="header-title">添加饮水记录</text>
        <text class="header-subtitle">记录每次饮水量，保持充足水分摄入</text>
      </view>

      <view class="form-card">
        <text class="form-label">日期</text>
        <input
          class="custom-input"
          v-model="form.date"
          placeholder="2000-01-01"
          placeholder-class="input-placeholder"
        />
        <text class="input-hint">格式：YYYY-MM-DD</text>

        <text class="form-label">饮水量</text>
        <view class="number-input-wrapper">
          <input
            class="custom-input"
            v-model="form.amountMl"
            type="digit"
            placeholder="例如：250"
            placeholder-class="input-placeholder"
          />
          <text class="unit-text">毫升</text>
        </view>
        <text class="input-hint">一杯水约 200~250 毫升</text>

        <button class="submit-btn" :disabled="submitting" @click="submitForm">
          {{ submitting ? '保存中...' : '保存记录' }}
        </button>
      </view>

      <view class="tip-card">
        <text class="tip-text">💡 成人每日建议饮水量约 1500~2000 毫升，运动或高温环境下需适当增加。少量多次饮水更有利于身体吸收。</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useThemeStore } from '@/store/theme'
import { waterApi } from '@/utils/api'

const themeStore = useThemeStore()
const { isDark } = themeStore

const today = new Date().toISOString().slice(0, 10)
const form = reactive({ date: today, amountMl: '' })
const submitting = ref(false)

const isValidDate = (d) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return false
  const date = new Date(d)
  return !isNaN(date.getTime())
}

const submitForm = async () => {
  if (submitting.value) return

  if (!form.date || !isValidDate(form.date)) {
    uni.showToast({ title: '请输入有效日期', icon: 'none' })
    return
  }
  const amount = parseFloat(form.amountMl)
  if (!amount || amount <= 0) {
    uni.showToast({ title: '请输入有效的饮水量', icon: 'none' })
    return
  }

  submitting.value = true
  try {
    await waterApi.add({ date: form.date, amountMl: amount })
    uni.showToast({ title: '添加成功', icon: 'success', duration: 1500 })
    uni.$emit('historyRefresh')
    setTimeout(() => uni.navigateBack(), 1500)
  } catch (e) {
    uni.showToast({ title: e.message || '添加失败', icon: 'error' })
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.form-page {
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
  background: radial-gradient(circle, rgba(6, 182, 212, 0.15), rgba(6, 182, 212, 0));
}

.form-container {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 32rpx 80rpx;
}

.header {
  text-align: center;
  margin-bottom: 48rpx;
}

.header-icon-wrapper {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.2), rgba(14, 165, 233, 0.2));
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24rpx;
  box-shadow: 0 16rpx 32rpx rgba(6, 182, 212, 0.2);
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

.form-card {
  width: 100%;
  max-width: 650rpx;
  background: var(--card-bg);
  border-radius: 56rpx;
  padding: 48rpx 40rpx 60rpx;
  box-shadow: 0 32rpx 64rpx rgba(0, 0, 0, 0.08);
  margin-bottom: 40rpx;
}

.form-label {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16rpx;
  margin-top: 28rpx;
}

.form-label:first-child {
  margin-top: 0;
}

.custom-input {
  height: 88rpx;
  background: var(--input-bg);
  border: 1.5px solid var(--input-border);
  border-radius: 24rpx;
  padding: 0 24rpx;
  font-size: 30rpx;
  color: var(--text-primary);
}

.custom-input:focus {
  border-color: #3b82f6;
  background: var(--card-bg);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.input-placeholder {
  color: var(--text-tertiary);
}

.input-hint {
  display: block;
  font-size: 24rpx;
  color: var(--text-tertiary);
  margin-top: 8rpx;
  margin-bottom: 8rpx;
}

.number-input-wrapper {
  position: relative;
}

.unit-text {
  position: absolute;
  right: 24rpx;
  top: 50%;
  transform: translateY(-50%);
  font-size: 28rpx;
  color: var(--text-tertiary);
}

.submit-btn {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  background: linear-gradient(135deg, #06b6d4, #0891b2);
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 600;
  border: none;
  border-radius: 60rpx;
  margin-top: 48rpx;
  box-shadow: 0 12rpx 24rpx rgba(6, 182, 212, 0.25);
}

.submit-btn:active {
  transform: scale(0.98);
  box-shadow: 0 4rpx 12rpx rgba(6, 182, 212, 0.2);
}

.submit-btn[disabled] {
  opacity: 0.6;
}

.tip-card {
  width: 100%;
  max-width: 650rpx;
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.08), rgba(14, 165, 233, 0.08));
  border-radius: 32rpx;
  padding: 28rpx 32rpx;
  border: 1rpx solid rgba(6, 182, 212, 0.2);
}

.tip-text {
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.6;
}

@media (max-width: 550px) {
  .form-container {
    padding: 32rpx 24rpx 60rpx;
  }
  .form-card {
    padding: 36rpx 28rpx 48rpx;
    border-radius: 40rpx;
  }
  .header-title {
    font-size: 38rpx;
  }
  .submit-btn {
    height: 88rpx;
    line-height: 88rpx;
    font-size: 30rpx;
  }
}
</style>
