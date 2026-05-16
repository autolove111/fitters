<template>
  <view class="form-page">
    <view class="top-decoration"></view>

    <view class="form-container">
      <view class="form-header">
        <view class="header-icon-wrapper">
          <text class="header-icon">🍽️</text>
        </view>
        <text class="header-title">添加饮食记录</text>
        <text class="header-subtitle">记录每一餐，均衡营养搭配</text>
      </view>

      <!-- 表单卡片 -->
      <view class="form-card">
        <!-- 日期输入 -->
        <view class="form-row">
          <view class="form-label">📅 日期</view>
          <input 
            v-model="form.date" 
            type="text"
            placeholder="例如：2000-01-01" 
            placeholder-class="input-placeholder"
            class="custom-input"
            maxlength="10"
          />
          <view class="input-hint">格式：YYYY-MM-DD</view>
        </view>

        <!-- 食物名称 -->
        <view class="form-row">
          <view class="form-label">🍎 食物名称</view>
          <input 
            v-model="form.foodName" 
            placeholder="例如：苹果、鸡胸肉、米饭" 
            placeholder-class="input-placeholder"
            class="custom-input"
          />
        </view>

        <!-- 热量（带单位） -->
        <view class="form-row">
          <view class="form-label">🔥 热量</view>
          <view class="number-input-wrapper">
            <input 
              v-model.number="form.calories" 
              type="number" 
              placeholder="千卡" 
              placeholder-class="input-placeholder"
              class="custom-input number-input"
            />
            <text class="unit-text">千卡</text>
          </view>
        </view>

        <!-- 保存按钮 -->
        <button 
          type="primary" 
          class="submit-btn" 
          :class="{ 'btn-loading': submitting }"
          :disabled="submitting"
          @click="submit"
        >
          <text v-if="!submitting">保存记录</text>
          <text v-else>保存中...</text>
        </button>
      </view>

      <!-- 提示小贴士卡片 -->
      <view class="tip-card">
        <text class="tip-icon">💡</text>
        <text class="tip-text">成年男性日均摄入约2250千卡，女性约1800千卡，合理搭配更健康</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { dietApi } from '@/utils/api'

const form = reactive({
  date: new Date().toISOString().slice(0, 10),
  foodName: '',
  calories: ''
})

const submitting = ref(false)

// 数字校验（正数）
const isValidPositiveNumber = (val) => {
  const num = parseFloat(val)
  return !isNaN(num) && num > 0
}

// 日期格式校验
const isValidDate = (dateStr) => {
  const regex = /^\d{4}-\d{2}-\d{2}$/
  if (!regex.test(dateStr)) return false
  const date = new Date(dateStr)
  return date instanceof Date && !isNaN(date)
}

async function submit() {
  // 日期校验
  if (!form.date) {
    uni.showToast({ title: '请填写日期', icon: 'none' })
    return
  }
  if (!isValidDate(form.date)) {
    uni.showToast({ title: '日期格式错误，请使用 YYYY-MM-DD 格式', icon: 'none' })
    return
  }

  // 食物名称校验
  if (!form.foodName.trim()) {
    uni.showToast({ title: '请填写食物名称', icon: 'none' })
    return
  }

  // 热量校验
  if (!form.calories || !isValidPositiveNumber(form.calories)) {
    uni.showToast({ title: '请填写有效的热量（>0）', icon: 'none' })
    return
  }

  if (submitting.value) return
  submitting.value = true

  try {
    await dietApi.add({
      date: form.date,
      foodName: form.foodName.trim(),
      calories: parseFloat(form.calories)
    })
    uni.showToast({ title: '添加成功', icon: 'success', duration: 1500 })
    if (uni && typeof uni.$emit === 'function') {
      uni.$emit('historyRefresh')
    }
    setTimeout(() => uni.navigateBack(), 1500)
  } catch (e) {
    uni.showToast({ title: e.message || '添加失败', icon: 'error' })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
/* 页面整体背景 */
.form-page {
  min-height: 100vh;
  background: linear-gradient(145deg, #f0f4f8 0%, #e6edf4 100%);
  position: relative;
  overflow-x: hidden;
}

.top-decoration {
  position: absolute;
  top: -80rpx;
  right: -80rpx;
  width: 300rpx;
  height: 300rpx;
  background: radial-gradient(circle, rgba(64,158,255,0.15) 0%, rgba(64,158,255,0) 70%);
  border-radius: 50%;
  pointer-events: none;
}

.form-container {
  padding: 40rpx 32rpx 80rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* 头部 */
.form-header {
  text-align: center;
  margin-bottom: 48rpx;
  width: 100%;
}

.header-icon-wrapper {
  width: 120rpx;
  height: 120rpx;
  background: linear-gradient(135deg, #409eff20 0%, #2c6ed120 100%);
  border-radius: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 24rpx;
  box-shadow: 0 8rpx 20rpx rgba(64,158,255,0.2);
}

.header-icon {
  font-size: 64rpx;
}

.header-title {
  font-size: 48rpx;
  font-weight: 700;
  background: linear-gradient(135deg, #1e2b3c, #2c4c6c);
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  letter-spacing: 2rpx;
  display: block;
  margin-bottom: 12rpx;
}

.header-subtitle {
  font-size: 26rpx;
  color: #8e9eae;
  letter-spacing: 0.5rpx;
}

/* 表单卡片 */
.form-card {
  width: 100%;
  max-width: 650rpx;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 56rpx;
  box-shadow: 0 24rpx 48rpx rgba(0, 0, 0, 0.08), 0 8rpx 16rpx rgba(0, 0, 0, 0.02);
  padding: 48rpx 40rpx 60rpx;
  margin-bottom: 30rpx;
}

/* 表单项行 */
.form-row {
  margin-bottom: 32rpx;
}

.form-label {
  font-size: 30rpx;
  font-weight: 600;
  color: #2c3e4e;
  line-height: 1.4;
  padding-bottom: 8rpx;
  display: block;
  text-align: left;
}

/* 输入框统一样式 */
.custom-input {
  width: 100%;
  height: 88rpx;
  background-color: #f8fafd;
  border: 2rpx solid #e2e8f0;
  border-radius: 24rpx;
  padding: 0 28rpx;
  font-size: 30rpx;
  color: #1e2a3a;
  transition: all 0.25s;
  box-sizing: border-box;
}

.custom-input:focus {
  border-color: #3b82f6;
  background-color: #ffffff;
  outline: none;
  box-shadow: 0 0 0 4rpx rgba(59,130,246,0.15);
}

.input-placeholder {
  color: #b9c4ce;
  font-size: 28rpx;
}

.input-hint {
  font-size: 22rpx;
  color: #9aaebf;
  margin-top: 8rpx;
  margin-left: 12rpx;
}

/* 带单位的数字输入框 */
.number-input-wrapper {
  position: relative;
  width: 100%;
}

.number-input {
  padding-right: 88rpx;
}

.unit-text {
  position: absolute;
  right: 28rpx;
  top: 50%;
  transform: translateY(-50%);
  font-size: 28rpx;
  color: #6c86a3;
  font-weight: 500;
  pointer-events: none;
  background-color: transparent;
}

/* 保存按钮 */
.submit-btn {
  margin-top: 56rpx;
  background: linear-gradient(105deg, #2c6e9e 0%, #1e4a76 100%);
  border-radius: 60rpx;
  height: 96rpx;
  line-height: 96rpx;
  font-size: 34rpx;
  font-weight: 600;
  color: white;
  box-shadow: 0 12rpx 24rpx rgba(28, 78, 118, 0.25);
  transition: all 0.3s ease;
  border: none;
  letter-spacing: 2rpx;
}

.submit-btn::after {
  border: none;
}

.submit-btn:active {
  transform: scale(0.97);
  box-shadow: 0 6rpx 12rpx rgba(0, 0, 0, 0.1);
  background: linear-gradient(105deg, #1e5a82 0%, #133e60 100%);
}

.btn-loading {
  opacity: 0.7;
  transform: scale(0.98);
}

/* 底部提示卡片 */
.tip-card {
  background: linear-gradient(135deg, #ecf5ff 0%, #f0f9ff 100%);
  border-radius: 32rpx;
  padding: 28rpx 32rpx;
  display: flex;
  align-items: center;
  gap: 20rpx;
  max-width: 650rpx;
  width: 100%;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.03);
  border: 1rpx solid rgba(64,158,255,0.2);
}

.tip-icon {
  font-size: 44rpx;
}

.tip-text {
  flex: 1;
  font-size: 26rpx;
  color: #2c5a7a;
  line-height: 1.4;
  font-weight: 500;
}

/* 小屏幕适配 */
@media (max-width: 550px) {
  .form-container {
    padding: 30rpx 24rpx 60rpx;
  }
  .form-card {
    padding: 36rpx 28rpx 48rpx;
  }
  .submit-btn {
    height: 88rpx;
    line-height: 88rpx;
    font-size: 32rpx;
  }
  .header-title {
    font-size: 42rpx;
  }
}
</style>