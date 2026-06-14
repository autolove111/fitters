<template>
  <view class="page">
    <view class="section">
      <view class="section-title">AI Personalized Fitness Plan</view>
      <view class="membership-row">
        <text class="tier">Current: {{ membership.tier }}</text>
        <text class="quota">Quota: {{ membership.remainingAiQuota }} / {{ membership.dailyAiQuota }}</text>
      </view>
      <view class="toggle-row">
        <button class="tier-btn" :class="{ active: membership.tier === 'FREE' }" @click="switchTier('FREE')">Free</button>
        <button class="tier-btn" :class="{ active: membership.tier === 'PRO' }" @click="switchTier('PRO')">Pro</button>
      </view>
    </view>

    <view class="section">
      <view class="section-title">Fitness Profile</view>
      <input class="input" type="number" v-model.number="profile.age" placeholder="Age" />
      <input class="input" type="number" v-model.number="profile.heightCm" placeholder="Height cm" />
      <input class="input" type="digit" v-model.number="profile.weightKg" placeholder="Weight kg" />
      <input class="input" v-model="profile.goal" placeholder="Goal, e.g. fat_loss / muscle_gain" />
      <picker :range="fitnessLevels" @change="onLevelChange">
        <view class="picker">Level: {{ profile.fitnessLevel }}</view>
      </picker>
      <input class="input" v-model="profile.injuries" placeholder="Injuries or limitations" />
      <input class="input" v-model="equipmentText" placeholder="Equipment, comma separated" />
      <picker :range="preferredTimes" @change="onTimeChange">
        <view class="picker">Preferred time: {{ profile.preferredWorkoutTime }}</view>
      </picker>
      <button class="secondary-btn" @click="saveProfile" :disabled="saving">Save Profile</button>
    </view>

    <view class="section">
      <view class="section-title">Generate Plan</view>
      <textarea class="textarea" v-model="question" placeholder="Optional: tell AI what you want today" />
      <button class="primary-btn" @click="generatePlan" :disabled="generating">
        {{ generating ? 'Generating...' : 'Generate Personalized Plan' }}
      </button>
    </view>

    <view v-if="planText" class="section result">
      <view class="section-title">Generated Result</view>
      <text class="plan-text">{{ planText }}</text>
    </view>
  </view>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { fitnessProfileApi, membershipApi, statsApi } from '@/utils/api'
import { formatAiPlanForDisplay } from '@/utils/aiPlanFormatter.mjs'

const fitnessLevels = ['beginner', 'intermediate', 'advanced']
const preferredTimes = ['morning', 'afternoon', 'evening']

const saving = ref(false)
const generating = ref(false)
const question = ref('')
const planText = ref('')
const membership = ref({ tier: 'FREE', dailyAiQuota: 3, remainingAiQuota: 3 })
const profile = ref({
  age: null,
  heightCm: null,
  weightKg: null,
  goal: 'general_fitness',
  fitnessLevel: 'beginner',
  injuries: '',
  equipment: [],
  preferredWorkoutTime: 'evening'
})

const equipmentText = computed({
  get: () => (profile.value.equipment || []).join(', '),
  set: (value) => {
    profile.value.equipment = String(value || '')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
  }
})

function onLevelChange(event) {
  profile.value.fitnessLevel = fitnessLevels[Number(event.detail.value)] || 'beginner'
}

function onTimeChange(event) {
  profile.value.preferredWorkoutTime = preferredTimes[Number(event.detail.value)] || 'evening'
}

async function loadInitialData() {
  try {
    const [profileData, membershipData] = await Promise.all([
      fitnessProfileApi.get(),
      membershipApi.get()
    ])
    profile.value = { ...profile.value, ...profileData }
    membership.value = { ...membership.value, ...membershipData }
  } catch (error) {
    uni.showToast({ title: error.message || 'Load failed', icon: 'none' })
  }
}

async function saveProfile() {
  saving.value = true
  try {
    const saved = await fitnessProfileApi.save(profile.value)
    profile.value = { ...profile.value, ...saved }
    uni.showToast({ title: 'Profile saved', icon: 'success' })
  } catch (error) {
    uni.showToast({ title: error.message || 'Save failed', icon: 'none' })
  } finally {
    saving.value = false
  }
}

async function switchTier(tier) {
  try {
    membership.value = { ...membership.value, ...(await membershipApi.setMockTier(tier)) }
  } catch (error) {
    uni.showToast({ title: error.message || 'Switch failed', icon: 'none' })
  }
}

async function generatePlan() {
  generating.value = true
  planText.value = ''
  try {
    await fitnessProfileApi.save(profile.value)
    const result = await statsApi.generatePersonalizedPlan({
      requestedDays: membership.value.tier === 'PRO' ? 30 : 7,
      question: question.value,
      goal: profile.value.goal,
      injuries: profile.value.injuries,
      equipment: profile.value.equipment,
      preferredTime: profile.value.preferredWorkoutTime
    })
    planText.value = formatAiPlanForDisplay(result)
    if (result.membership) {
      membership.value = { ...membership.value, ...result.membership }
    }
  } catch (error) {
    uni.showToast({ title: error.message || 'Generate failed', icon: 'none' })
  } finally {
    generating.value = false
  }
}

onMounted(loadInitialData)
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 28rpx;
  background: #f5f7fa;
}

.section {
  background: #ffffff;
  border-radius: 16rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.04);
}

.section-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #263238;
  margin-bottom: 20rpx;
}

.membership-row {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  font-size: 26rpx;
  color: #455a64;
  margin-bottom: 20rpx;
}

.toggle-row {
  display: flex;
  gap: 16rpx;
}

.tier-btn,
.secondary-btn,
.primary-btn {
  border-radius: 12rpx;
  font-size: 28rpx;
}

.tier-btn {
  flex: 1;
  background: #eef2f6;
  color: #37474f;
}

.tier-btn.active {
  background: #1f7a5c;
  color: #ffffff;
}

.input,
.picker,
.textarea {
  box-sizing: border-box;
  width: 100%;
  min-height: 76rpx;
  padding: 18rpx 20rpx;
  margin-bottom: 18rpx;
  border: 1px solid #d8dee4;
  border-radius: 12rpx;
  background: #fbfcfd;
  font-size: 28rpx;
  color: #263238;
}

.textarea {
  min-height: 140rpx;
}

.secondary-btn {
  background: #e8f5ef;
  color: #1f7a5c;
}

.primary-btn {
  background: #1f7a5c;
  color: #ffffff;
}

.result {
  border-left: 8rpx solid #1f7a5c;
}

.plan-text {
  white-space: pre-line;
  font-size: 27rpx;
  line-height: 1.65;
  color: #37474f;
}
</style>
