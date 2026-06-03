<template>
  <view class="container">
    <!-- ========= 未登录：高级登录卡片 ========= -->
    <view v-if="!isLoggedIn" class="auth-card">
      <view class="auth-bg-glow"></view>
      <view class="logo-section">
        <view class="logo-circle">
          <text class="logo-emoji">✨</text>
        </view>
        <text class="logo-text">Fitters</text>
        <text class="logo-caption">健康 · 平衡 · 生命力</text>
      </view>

      <view class="input-field">
        <text class="field-icon">📧</text>
        <input v-model="account" placeholder="账号 / 邮箱" placeholder-class="placeholder-light" />
      </view>
      <view class="input-field">
        <text class="field-icon">🔒</text>
        <input v-model="password" :password="!showPassword" placeholder="密码" placeholder-class="placeholder-light" />
        <text class="pwd-toggle" @click="togglePasswordVisibility">{{ showPassword ? '🙈' : '👁️' }}</text>
      </view>

      <view class="auth-buttons">
        <button class="btn-primary" @click="handleLogin">登录</button>
        <button class="btn-outline" @click="handleRegister">注册</button>
      </view>
      <text v-if="authError" class="error-tip">{{ authError }}</text>
    </view>

    <!-- ========= 已登录：高级仪表板 ========= -->
    <view v-else class="dashboard">
      <!-- 背景装饰层 -->
      <view class="bg-blur"></view>
      <view class="bg-orbs">
        <view class="orb o1"></view>
        <view class="orb o2"></view>
        <view class="orb o3"></view>
      </view>

      <!-- 顶部用户卡片 -->
      <view class="user-card">
        <view class="user-avatar" @click="viewAvatar">
          <image v-if="userAvatar" :src="userAvatar" mode="aspectFill" />
          <text v-else class="avatar-placeholder">🧘</text>
        </view>
        <view class="user-details">
          <text class="greeting">🌿 你好，{{ displayName }}</text>
          <text class="date">{{ currentDate }}</text>
        </view>
        <view class="settings-btn" @click="goProfile">
          <text>⚙️</text>
        </view>
      </view>

      <!-- 2x2 功能网格 -->
      <view class="menu-grid">
        <view class="menu-item" v-for="item in menuItems" :key="item.id" @click="item.handler">
          <view class="item-glow"></view>
          <view class="item-icon" :style="{ background: item.gradient }">
            <text>{{ item.emoji }}</text>
          </view>
          <text class="item-title">{{ item.title }}</text>
          <text class="item-desc">{{ item.desc }}</text>
        </view>
      </view>

      <!-- 今日微习惯卡片 -->
      <view class="habit-card">
        <view class="habit-left">
          <text class="habit-icon">🌱</text>
          <view class="habit-text">
            <text class="habit-label">今日微习惯</text>
            <text class="habit-content">{{ dailyTip }}</text>
          </view>
        </view>
        <view class="habit-sparkle">✨</view>
      </view>

      <!-- 底部装饰文字 -->
      <view class="footer-note">每一次微小坚持，都在塑造更好的你</view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/store/user'
import { auth } from '@/utils/api'

const userStore = useUserStore()
const { isLoggedIn, state, displayName, setUser, loadAvatar, loadProfile } = userStore
const userAvatar = computed(() => state.avatar || '')

onShow(() => {
  loadAvatar()
  loadProfile()
})

const viewAvatar = () => {
  if (!userAvatar.value) {
    uni.showToast({ title: '暂无头像', icon: 'none' })
    return
  }
  uni.previewImage({ urls: [userAvatar.value], current: userAvatar.value })
}

// 登录表单
const account = ref('demo')
const password = ref('demo123')
const authError = ref('')
const showPassword = ref(false)

const currentDate = computed(() => {
  const now = new Date()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${month}.${day} · ${weekdays[now.getDay()]}`
})

const tipsList = [
  '深呼吸三次，感受当下的平静', '喝一杯温水，唤醒身体活力', '伸展四肢五分钟，缓解久坐疲劳',
  '放下手机十分钟，让眼睛休息', '微笑一下，释放积极能量', '走楼梯代替电梯，多消耗卡路里',
  '记录一件感恩的小事', '午餐细嚼慢咽，专注每一口', '站立办公半小时，改善体态',
  '眺望远方，给眼睛放个假', '睡前冥想五分钟，提高睡眠质量', '主动夸奖一个人，温暖彼此'
]
const dailyTip = computed(() => {
  const dayOfYear = Math.floor((new Date() - new Date(new Date().getFullYear(), 0, 0)) / 86400000)
  return tipsList[dayOfYear % tipsList.length]
})

// 菜单配置（2x2网格，对应原有功能）
const menuItems = [
  { id: 1, title: '健康', desc: '综合健康管理', emoji: '❤️‍🔥', gradient: 'linear-gradient(135deg, #3b82f6, #1e3a8a)', handler: () => uni.navigateTo({ url: '/pages/workout/workout' }) },
  { id: 2, title: '减肥', desc: '科学减脂计划', emoji: '🥗', gradient: 'linear-gradient(135deg, #10b981, #047857)', handler: () => uni.navigateTo({ url: '/pages/weightloss/weightloss' }) },
  { id: 3, title: '工作', desc: '效率与专注', emoji: '💼', gradient: 'linear-gradient(135deg, #f59e0b, #b45309)', handler: () => uni.navigateTo({ url: '/pages/work/work' }) },
  { id: 4, title: '学习', desc: '学习计划与助手', emoji: '📚', gradient: 'linear-gradient(135deg, #8b5cf6, #5b21b6)', handler: () => uni.navigateTo({ url: '/pages/study/index' }) }
]

function togglePasswordVisibility() { showPassword.value = !showPassword.value }
async function handleLogin() {
  authError.value = ''
  try {
    const res = await auth.login(account.value, password.value)
    setUser(res.token, res.user.account)
    uni.showToast({ title: '登录成功', icon: 'success' })
  } catch (e) {
    authError.value = e.message
    uni.showToast({ title: e.message, icon: 'none' })
  }
}
function handleRegister() { uni.navigateTo({ url: '/pages/register/register' }) }
function goProfile() { uni.navigateTo({ url: '/pages/profile/index' }) }
</script>

<style scoped>
/* 全局变量 */
.container {
  padding: 32rpx;
  min-height: 100vh;
  background: radial-gradient(circle at 10% 20%, #f8fafc, #eef2ff);
  position: relative;
}

/* ========= 登录卡片 ========= */
.auth-card {
  margin-top: 100rpx;
  padding: 60rpx 40rpx;
  background: rgba(255,255,255,0.7);
  backdrop-filter: blur(30rpx);
  border-radius: 80rpx;
  box-shadow: 0 30rpx 60rpx -20rpx rgba(0,0,0,0.2), 0 0 0 1rpx rgba(255,255,255,0.6) inset;
  position: relative;
  overflow: hidden;
}
.auth-bg-glow {
  position: absolute;
  top: -30%;
  left: -20%;
  width: 140%;
  height: 140%;
  background: radial-gradient(circle, rgba(59,130,246,0.15), transparent);
  pointer-events: none;
}
.logo-section { text-align: center; margin-bottom: 60rpx; }
.logo-circle {
  width: 120rpx;
  height: 120rpx;
  background: linear-gradient(145deg, #3b82f6, #1e3a8a);
  border-radius: 60rpx;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 20rpx 30rpx -10rpx rgba(59,130,246,0.4);
  margin-bottom: 24rpx;
}
.logo-emoji { font-size: 64rpx; }
.logo-text { font-size: 56rpx; font-weight: 800; background: linear-gradient(135deg, #1e293b, #2d3e5f); -webkit-background-clip: text; background-clip: text; color: transparent; display: block; }
.logo-caption { font-size: 24rpx; color: #6b7280; margin-top: 12rpx; letter-spacing: 2rpx; }

.input-field {
  position: relative;
  margin-bottom: 32rpx;
  background: rgba(255,255,255,0.9);
  border-radius: 60rpx;
  height: 100rpx;
  display: flex;
  align-items: center;
  padding: 0 24rpx;
  border: 1rpx solid rgba(0,0,0,0.05);
  transition: all 0.2s;
}
.input-field:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 6rpx rgba(59,130,246,0.1);
}
.field-icon { font-size: 36rpx; margin-right: 20rpx; opacity: 0.6; }
.input-field input { flex: 1; font-size: 32rpx; color: #1f2937; }
.pwd-toggle { font-size: 36rpx; padding: 10rpx; }
.placeholder-light { color: #9ca3af; }

.auth-buttons { display: flex; gap: 24rpx; margin-top: 48rpx; }
.btn-primary, .btn-outline {
  flex: 1;
  height: 96rpx;
  border-radius: 60rpx;
  font-size: 32rpx;
  font-weight: 600;
  border: none;
  transition: all 0.2s;
}
.btn-primary {
  background: linear-gradient(105deg, #3b82f6, #1e40af);
  color: white;
  box-shadow: 0 12rpx 24rpx -8rpx rgba(59,130,246,0.5);
}
.btn-primary:active { transform: scale(0.97); }
.btn-outline {
  background: rgba(255,255,255,0.9);
  color: #374151;
  border: 1rpx solid #d1d5db;
}
.btn-outline:active { transform: scale(0.97); background: #f9fafb; }
.error-tip { color: #ef4444; text-align: center; margin-top: 24rpx; display: block; }

/* ========= 已登录仪表板 ========= */
.dashboard { position: relative; display: flex; flex-direction: column; gap: 36rpx; z-index: 2; }

/* 背景光晕 */
.bg-blur {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: radial-gradient(circle at 20% 30%, rgba(59,130,246,0.08), transparent 70%);
  pointer-events: none;
}
.bg-orbs { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80rpx);
  opacity: 0.4;
  animation: float 20s infinite;
}
.o1 { width: 400rpx; height: 400rpx; background: #60a5fa; top: -100rpx; right: -100rpx; }
.o2 { width: 300rpx; height: 300rpx; background: #a78bfa; bottom: 20%; left: -80rpx; animation-delay: -5s; }
.o3 { width: 250rpx; height: 250rpx; background: #34d399; top: 40%; right: -50rpx; animation-delay: -10s; }
@keyframes float {
  0%,100% { transform: translateY(0) translateX(0); }
  50% { transform: translateY(-30rpx) translateX(20rpx); }
}

/* 用户卡片 */
.user-card {
  background: rgba(255,255,255,0.75);
  backdrop-filter: blur(30rpx);
  border-radius: 48rpx;
  padding: 24rpx;
  display: flex;
  align-items: center;
  gap: 24rpx;
  border: 1rpx solid rgba(255,255,255,0.8);
  box-shadow: 0 15rpx 35rpx -12rpx rgba(0,0,0,0.05);
}
.user-avatar {
  width: 96rpx;
  height: 96rpx;
  background: linear-gradient(145deg, #e0e7ff, #ffffff);
  border-radius: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-shadow: 0 8rpx 20rpx -6rpx rgba(0,0,0,0.1);
}
.user-avatar image { width: 100%; height: 100%; }
.avatar-placeholder { font-size: 52rpx; }
.user-details { flex: 1; }
.greeting { font-size: 34rpx; font-weight: 700; color: #111827; display: block; }
.date { font-size: 24rpx; color: #6b7280; margin-top: 6rpx; display: block; }
.settings-btn {
  width: 72rpx;
  height: 72rpx;
  background: rgba(0,0,0,0.03);
  border-radius: 40rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
  transition: all 0.2s;
}
.settings-btn:active { transform: scale(0.92); background: rgba(0,0,0,0.08); }

/* 2x2 网格菜单 */
.menu-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28rpx;
}
.menu-item {
  position: relative;
  background: rgba(255,255,255,0.7);
  backdrop-filter: blur(20rpx);
  border-radius: 48rpx;
  padding: 36rpx 20rpx 32rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  transition: all 0.3s cubic-bezier(0.2,0.9,0.4,1.2);
  border: 1rpx solid rgba(255,255,255,0.9);
  box-shadow: 0 12rpx 30rpx -10rpx rgba(0,0,0,0.05);
  overflow: hidden;
}
.menu-item:active {
  transform: scale(0.96);
  box-shadow: 0 6rpx 16rpx -8rpx rgba(0,0,0,0.1);
}
.item-glow {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255,255,255,0.4), transparent);
  opacity: 0;
  transition: opacity 0.3s;
  pointer-events: none;
}
.menu-item:active .item-glow { opacity: 0.6; }
.item-icon {
  width: 100rpx;
  height: 100rpx;
  border-radius: 36rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 20rpx -6rpx rgba(0,0,0,0.15);
}
.item-icon text { font-size: 56rpx; }
.item-title { font-size: 34rpx; font-weight: 800; color: #111827; margin-bottom: 8rpx; }
.item-desc { font-size: 22rpx; color: #6b7280; font-weight: 500; }

/* 习惯卡片 */
.habit-card {
  background: rgba(255,255,255,0.8);
  backdrop-filter: blur(30rpx);
  border-radius: 48rpx;
  padding: 28rpx 32rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1rpx solid rgba(255,255,255,0.8);
  box-shadow: 0 15rpx 35rpx -12rpx rgba(0,0,0,0.05);
}
.habit-left { display: flex; align-items: center; gap: 20rpx; flex: 1; }
.habit-icon { font-size: 48rpx; background: linear-gradient(135deg, #34d399, #10b981); width: 72rpx; height: 72rpx; border-radius: 36rpx; display: flex; align-items: center; justify-content: center; }
.habit-text { flex: 1; }
.habit-label { font-size: 22rpx; font-weight: 600; color: #10b981; display: block; margin-bottom: 6rpx; letter-spacing: 1rpx; }
.habit-content { font-size: 28rpx; font-weight: 600; color: #1f2937; display: block; }
.habit-sparkle { font-size: 40rpx; animation: float 2s infinite; }

/* 底部文字 */
.footer-note {
  text-align: center;
  font-size: 24rpx;
  color: #9ca3af;
  padding: 20rpx 0 40rpx;
  letter-spacing: 1rpx;
}
</style>