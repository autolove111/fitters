<template>
  <scroll-view class="detail-container" :class="{ dark: isDark }" scroll-y>
    <!-- 顶部 Hero -->
    <view class="hero-section">
      <view class="hero-bg-circle"></view>
      <text class="exercise-icon">{{ exercise.icon }}</text>
      <text class="exercise-name">{{ exercise.name }}</text>
      <view class="hero-tags">
        <text class="hero-tag">微运动</text>
        <text class="hero-tag">{{ stepCount }} 个步骤</text>
        <text class="hero-tag">随时可做</text>
      </view>
    </view>

    <!-- 动作说明 -->
    <view class="section-card instruction-card">
      <view class="section-header">
        <view class="section-icon">📖</view>
        <view>
          <text class="section-title">动作说明</text>
          <text class="section-subtitle">按步骤完成动作</text>
        </view>
      </view>
      <view class="steps-list">
        <view v-for="(step, idx) in steps" :key="idx" class="step-item">
          <view class="step-number">{{ idx + 1 }}</view>
          <text class="step-text">{{ step }}</text>
        </view>
      </view>
    </view>

    <!-- 小贴士 -->
    <view class="section-card tips-card" v-if="tips">
      <view class="section-header">
        <view class="section-icon">💡</view>
        <view>
          <text class="section-title">小贴士</text>
          <text class="section-subtitle">让运动更有效</text>
        </view>
      </view>
      <text class="tips-text">{{ tips }}</text>
    </view>

    <!-- 底部操作 -->
    <view class="bottom-actions">
      <button class="back-btn" @click="goBack">
        <text class="back-btn-text">返回工作主页</text>
      </button>
    </view>
  </scroll-view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useThemeStore } from '@/store/theme'
const themeStore = useThemeStore()
const { isDark } = themeStore

const exercise = ref({})
const instruction = ref('')
const tips = ref('')

const steps = computed(() => {
  if (!instruction.value) return []
  return instruction.value
    .split('\n')
    .map(s => s.replace(/^\d+\.\s*/, '').trim())
    .filter(Boolean)
})

const stepCount = computed(() => steps.value.length || 1)

// 动作库（ID 与 work.vue 中的 id 对应）
const exercisesMap = {
  1: { name: '手腕屈伸', icon: '✋', instruction: '1. 双臂前伸，手掌向上。\n2. 轻轻弯曲手腕，手指指向地面。\n3. 保持5秒，缓慢复位。\n4. 重复10次。', tips: '每天做2-3组，可缓解鼠标手。' },
  2: { name: '颈部侧屈', icon: '🦒', instruction: '1. 坐直，肩膀放松。\n2. 慢慢将头倒向右侧，耳朵靠近肩膀。\n3. 保持10秒，回到中间。\n4. 换左侧重复。', tips: '避免耸肩，轻柔拉伸。' },
  3: { name: '20-20-20护眼', icon: '👀', instruction: '每工作20分钟，抬头看20英尺（约6米）外的物体，持续20秒。', tips: '设置定时器提醒自己。' },
  4: { name: '踮脚尖', icon: '🦶', instruction: '1. 站立，双脚与肩同宽。\n2. 缓慢踮起脚尖，保持5秒。\n3. 缓慢落下。重复15次。', tips: '可手扶墙壁保持平衡。' },
  5: { name: '深呼吸放松', icon: '🌬️', instruction: '1. 坐直，闭眼。\n2. 用鼻子深吸气4秒。\n3. 屏息2秒。\n4. 用嘴缓慢呼气6秒。重复5次。', tips: '帮助缓解声带疲劳和紧张情绪。' },
  6: { name: '腰背拉伸', icon: '🧘', instruction: '1. 坐在椅子上，双脚平放。\n2. 双手交叉抱住后脑勺。\n3. 轻轻向后仰，感受背部拉伸。\n4. 保持10秒，缓慢回正。', tips: '动作要慢，避免腰部受伤。' },
  7: { name: '脚踝泵', icon: '🦶', instruction: '1. 坐姿，双脚离地。\n2. 用力勾脚尖，保持5秒。\n3. 用力绷直脚尖，保持5秒。\n4. 重复10次。', tips: '促进下肢血液循环，预防静脉血栓。' },
  8: { name: '眼保健操', icon: '👁️', instruction: '1. 按揉攒竹穴（眉头）。\n2. 按压睛明穴（鼻梁根部）。\n3. 揉四白穴（颧骨下方）。\n4. 轮刮眼眶。', tips: '每个动作做4个八拍，力度适中。' },
  9: { name: '脊柱扭转', icon: '🔄', instruction: '1. 坐直，左手放右膝，右手扶椅背。\n2. 吸气，身体向右扭转。\n3. 呼气，加深扭转。保持5个呼吸。\n4. 换另一侧。', tips: '感受脊柱的拉伸，不要用力过猛。' },
  10: { name: '肩部绕环', icon: '🔄', instruction: '1. 双臂自然下垂。\n2. 双肩向前画圈10次。\n3. 再向后画圈10次。', tips: '缓解肩颈酸痛。' },
  11: { name: '站立勾脚尖', icon: '🦶', instruction: '1. 站立，手扶椅背。\n2. 一只脚勾脚尖向上抬起，保持5秒。\n3. 换另一只脚。每只脚10次。', tips: '预防静脉曲张。' },
  12: { name: '座椅拉伸', icon: '🪑', instruction: '1. 坐直，双手举过头顶。\n2. 身体向左侧弯曲，右手抓住左手腕。\n3. 保持10秒，换右侧。', tips: '拉伸侧腰和脊柱。' },
  13: { name: '手腕绕环', icon: '✋', instruction: '1. 双手握拳，手腕顺时针画圈10次。\n2. 逆时针画圈10次。', tips: '动作轻柔，放松手腕。' },
  14: { name: '靠墙静蹲', icon: '🧎', instruction: '1. 背靠墙，双脚与肩同宽。\n2. 缓慢下蹲，大腿与地面平行。\n3. 保持30秒-1分钟。', tips: '膝盖不要超过脚尖。' },
  15: { name: '深呼吸放松', icon: '🌬️', instruction: '同深呼吸放松法', tips: '适合销售人员在见客户前使用。' },
  16: { name: '颈部拉伸', icon: '🦒', instruction: '同颈部侧屈', tips: '随时可做。' },
  17: { name: '坐姿转体', icon: '🔄', instruction: '1. 坐直，双手放后脑勺。\n2. 身体向左转，感觉背部拉伸。\n3. 保持5秒，回正。\n4. 换右侧。', tips: '活动胸椎和肩胛。' }
}

onMounted(() => {
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1]
  const options = currentPage.options
  const id = options.id
  if (id && exercisesMap[id]) {
    const data = exercisesMap[id]
    exercise.value = { name: data.name, icon: data.icon }
    instruction.value = data.instruction
    tips.value = data.tips
  } else {
    exercise.value = { name: '微运动', icon: '🧘' }
    instruction.value = '请从工作主页选择正确的动作'
    tips.value = ''
  }
})

const goBack = () => {
  uni.navigateBack()
}
</script>

<style scoped>
.detail-container {
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  box-sizing: border-box;
}

/* 顶部英雄区 */
.hero-section {
  position: relative;
  padding: 60rpx 30rpx 40rpx;
  text-align: center;
  overflow: hidden;
}

.hero-bg-circle {
  position: absolute;
  top: -80rpx;
  right: -60rpx;
  width: 280rpx;
  height: 280rpx;
  background: rgba(34, 197, 94, 0.1);
  border-radius: 50%;
}

.exercise-icon {
  font-size: 120rpx;
  display: block;
  margin-bottom: 20rpx;
  filter: drop-shadow(0 8rpx 16rpx rgba(0, 0, 0, 0.1));
}

.exercise-name {
  font-size: 52rpx;
  font-weight: 800;
  color: var(--text-primary);
  display: block;
  margin-bottom: 24rpx;
}

.hero-tags {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 14rpx;
}

.hero-tag {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
  padding: 10rpx 22rpx;
  border-radius: 999rpx;
  font-size: 24rpx;
  font-weight: 600;
}

/* 区域卡片 */
.section-card {
  margin: 0 30rpx 28rpx;
  padding: 30rpx;
  border-radius: 36rpx;
  backdrop-filter: blur(20rpx);
  border: 1rpx solid var(--card-border);
}

.instruction-card {
  background: var(--card-bg);
  box-shadow: 0 20rpx 44rpx rgba(34, 197, 94, 0.1);
}

.tips-card {
  background: var(--card-bg);
  box-shadow: 0 20rpx 44rpx rgba(251, 191, 36, 0.1);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 18rpx;
  margin-bottom: 26rpx;
}

.section-icon {
  width: 72rpx;
  height: 72rpx;
  border-radius: 24rpx;
  background: rgba(34, 197, 94, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
  flex-shrink: 0;
}

.tips-card .section-icon {
  background: rgba(251, 191, 36, 0.12);
}

.section-title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--text-primary);
  display: block;
}

.section-subtitle {
  font-size: 24rpx;
  color: var(--text-secondary);
  display: block;
  margin-top: 4rpx;
}

/* 步骤 */
.steps-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.step-item {
  display: flex;
  align-items: flex-start;
  gap: 18rpx;
}

.step-number {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #22c55e, #16a34a);
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 4rpx;
}

.step-text {
  flex: 1;
  font-size: 28rpx;
  line-height: 1.7;
  color: var(--text-primary);
}

/* 小贴士 */
.tips-text {
  font-size: 28rpx;
  line-height: 1.7;
  color: var(--text-primary);
  padding: 20rpx 24rpx;
  background: rgba(251, 191, 36, 0.08);
  border-radius: 20rpx;
  border-left: 6rpx solid rgba(251, 191, 36, 0.4);
}

/* 底部操作 */
.bottom-actions {
  padding: 16rpx 30rpx 60rpx;
}

.back-btn {
  width: 100%;
  height: 88rpx;
  border-radius: 999rpx;
  border: none;
  background: linear-gradient(135deg, #22c55e, #16a34a);
  box-shadow: 0 16rpx 32rpx rgba(34, 197, 94, 0.22);
  display: flex;
  align-items: center;
  justify-content: center;
}

.back-btn-text {
  font-size: 30rpx;
  font-weight: 700;
  color: #ffffff;
}
</style>
