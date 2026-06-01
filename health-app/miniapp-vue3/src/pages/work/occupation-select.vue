<template>
  <scroll-view class="select-container" :class="{ dark: isDark }" scroll-y>
    <view class="select-inner">
      <view class="header">
        <text class="title">选择您的职业</text>
        <text class="subtitle">获取专属健康管理方案</text>
      </view>
      <view class="occupation-grid">
        <view 
          v-for="occ in occupations" 
          :key="occ.value" 
          class="occ-card"
          @click="confirmOccupation(occ)"
        >
          <text class="occ-icon">{{ occ.icon }}</text>
          <text class="occ-name">{{ occ.label }}</text>
          <text class="occ-desc">{{ occ.desc }}</text>
        </view>
      </view>
    </view>
  </scroll-view>
</template>

<script setup>
import { ref } from 'vue'
import { useThemeStore } from '@/store/theme'
const themeStore = useThemeStore()
const { isDark } = themeStore

const occupations = [
  { value: 'it', label: 'IT/设计', icon: '💻', desc: '保护手腕与眼睛' },
  { value: 'teacher', label: '教育/培训', icon: '📚', desc: '多喝水，护嗓音' },
  { value: 'driver', label: '司机/物流', icon: '🚚', desc: '放松腰背，多活动' },
  { value: 'student', label: '学生', icon: '🎓', desc: '护眼课间动起来' },
  { value: 'medical', label: '医疗/护理', icon: '🏥', desc: '深呼吸，放松腿脚' },
  { value: 'admin', label: '行政/文员', icon: '📄', desc: '肩颈舒展' },
  { value: 'sales', label: '销售/外勤', icon: '🤝', desc: '走走更健康' },
  { value: 'general', label: '通用', icon: '🌟', desc: '动起来更健康' }
]

const confirmOccupation = (occ) => {
  uni.showModal({
    title: '切换职业',
    content: `确定要切换到「${occ.label}」模式吗？更换后职业专属数据将重置。`,
    confirmText: '确定',
    cancelText: '取消',
    success: (res) => {
      if (res.confirm) {
        uni.$emit('occupationChanged', { 
        value: occ.value, 
        label: occ.label 
        })
        uni.navigateBack()
      }
    }
  })
}
</script>

<style scoped>
/* 外层滚动容器 - 左右边距一致 */
.select-container {
  width: 100%;
  min-height: 100vh;
  overflow-x: hidden;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  box-sizing: border-box;
}

/* 内部内容容器，统一左右内边距 30rpx */
.select-inner {
  padding: 40rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
  width: 100%;
}

.header {
  text-align: center;
  margin-bottom: 60rpx;
}
.title {
  font-size: 52rpx;
  font-weight: 800;
  background: linear-gradient(135deg, #2e7d32, #66bb6a);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  display: block;
}
.subtitle {
  font-size: 28rpx;
  color: #558b2f;
  margin-top: 12rpx;
}
.occupation-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 30rpx;
}
.occ-card {
  background: var(--card-bg);
  border-radius: 48rpx;
  padding: 40rpx 20rpx;
  text-align: center;
  box-shadow: 0 8rpx 20rpx rgba(0,0,0,0.05);
  transition: all 0.2s;
}
.occ-card:active {
  transform: scale(0.97);
  background: #e8f5e9;
}
.occ-icon {
  font-size: 64rpx;
  display: block;
  margin-bottom: 16rpx;
}
.occ-name {
  font-size: 34rpx;
  font-weight: 700;
  color: #2e7d32;
  display: block;
  margin-bottom: 8rpx;
}
.occ-desc {
  font-size: 24rpx;
  color: var(--text-secondary);
}
</style>