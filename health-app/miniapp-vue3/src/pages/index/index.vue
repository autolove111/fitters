<template>
  <view class="container" :class="{ dark: isDark }">
    <!-- ========= 未登录：显示登录/注册表单 ========= -->
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
import { useThemeStore } from '@/store/theme'
import { auth } from '@/utils/api'

const themeStore = useThemeStore()
const { isDark } = themeStore

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
    setUser(res.token, res.user.account, res.user.nickname || '', res.user.avatar || '')
    await loadProfile()
    await loadAvatar()
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
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
}

/* ========= 登录卡片 ========= */
.auth-card {
  margin-top: 80rpx;
  padding: 50rpx 40rpx 60rpx;
  background: var(--card-bg);
  backdrop-filter: blur(20px);
  border-radius: 60rpx;
  box-shadow: 0 25rpx 50rpx -12rpx rgba(0, 0, 0, 0.15), 0 0 0 1rpx rgba(255, 255, 255, 0.6) inset;
}

.logo-area {
  text-align: center;
  margin-bottom: 48rpx;
}
.logo-icon {
  font-size: 64rpx;
  display: block;
  background: linear-gradient(135deg, #3b82f6, #1e3a8a);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin-bottom: 12rpx;
}
.logo-title {
  font-size: 44rpx;
  font-weight: 800;
  background: linear-gradient(135deg, #1e293b, #2d3e5f);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: -0.5rpx;
  display: block;
}
.logo-sub {
  font-size: 24rpx;
  color: #5b6e8c;
  margin-top: 12rpx;
  display: block;
  letter-spacing: 2rpx;
}

.auth-input {
  width: 100%;
  height: 96rpx;
  padding: 0 28rpx;
  margin-bottom: 32rpx;
  font-size: 32rpx;
  background: var(--input-bg);
  border-radius: 48rpx;
  border: 1.5px solid var(--input-border);
  box-sizing: border-box;
  transition: all 0.2s;
  color: var(--text-primary);
}
.auth-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 6rpx rgba(59, 130, 246, 0.15);
  background: var(--card-bg);
}

.password-wrapper {
  position: relative;
  width: 100%;
}
.password-input {
  padding-right: 140rpx;
  margin-bottom: 0;
}
.toggle-pwd-btn {
  position: absolute;
  right: 20rpx;
  top: 50%;
  transform: translateY(-50%);
  background: #eef2ff;
  padding: 10rpx 24rpx;
  border-radius: 60rpx;
  font-size: 26rpx;
  color: #3b82f6;
  font-weight: 600;
  transition: all 0.2s;
}
.toggle-pwd-btn:active {
  background: #d9e6ff;
  transform: translateY(-50%) scale(0.96);
}

.auth-actions {
  display: flex;
  gap: 24rpx;
  margin-top: 48rpx;
}
.auth-btn {
  flex: 1;
  height: 96rpx;
  line-height: 96rpx;
  border-radius: 60rpx;
  font-size: 32rpx;
  font-weight: 600;
  border: none;
  transition: all 0.2s;
}
.auth-btn.primary {
  background: linear-gradient(105deg, #2563eb, #1e40af);
  color: white;
  box-shadow: 0 12rpx 24rpx -10rpx rgba(37, 99, 235, 0.4);
}
.auth-btn.primary:active {
  transform: scale(0.97);
  box-shadow: 0 6rpx 16rpx -8rpx rgba(37, 99, 235, 0.5);
}
.auth-btn.secondary {
  background: var(--card-bg);
  color: var(--text-primary);
  border: 1px solid var(--input-border);
}
.auth-btn.secondary:active {
  transform: scale(0.97);
  background: var(--card-bg);
}
.error {
  color: #ef4444;
  font-size: 26rpx;
  margin-top: 24rpx;
  display: block;
  text-align: center;
  font-weight: 500;
}

/* ========= 已登录仪表板 ———— 丰富色彩 ========= */
.dashboard {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 44rpx;
  animation: fadeUp 0.5s cubic-bezier(0.2, 0.9, 0.4, 1.1);
  padding-bottom: 40rpx;
  z-index: 2;
}
@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(30rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 用户栏 */
.user-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(96, 165, 250, 0.18));
  backdrop-filter: blur(20rpx);
  border-radius: 40rpx;
  padding: 20rpx 24rpx 20rpx 20rpx;
  border: 1rpx solid var(--card-border);
  box-shadow: 0 22rpx 50rpx rgba(59, 130, 246, 0.12);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.avatar-ring {
  width: 80rpx;
  height: 80rpx;
  background: linear-gradient(135deg, #fff5e6, #ffffff);
  border-radius: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 16rpx -6rpx rgba(0, 0, 0, 0.05), 0 0 0 2rpx rgba(255, 255, 255, 0.8) inset;
  overflow: hidden;
}
.avatar-img {
  width: 80rpx;
  height: 80rpx;
  border-radius: 60rpx;
}

.avatar-emoji {
  font-size: 44rpx;
  filter: drop-shadow(0 2rpx 4rpx rgba(0, 0, 0, 0.1));
}

.user-text {
  display: flex;
  flex-direction: column;
}

.greeting {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3rpx;
  line-height: 1.3;
}

.today-date {
  font-size: 24rpx;
  color: var(--text-secondary);
  font-weight: 500;
  letter-spacing: 1rpx;
  margin-top: 6rpx;
}

.logout-btn {
  background: rgba(59, 130, 246, 0.12);
  backdrop-filter: blur(12rpx);
  border: none;
  border-radius: 999rpx;
  padding: 12rpx 32rpx;
  font-size: 26rpx;
  color: #2563eb;
  font-weight: 600;
  transition: all 0.2s ease;
  border: 1rpx solid var(--card-border);
}
.logout-btn:active {
  transform: scale(0.96);
  background: rgba(59, 130, 246, 0.2);
}

/* 功能卡片网格 */
.menu-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 32rpx;
  margin: 8rpx 0;
}

.menu-card {
  position: relative;
  backdrop-filter: blur(20rpx);
  border-radius: 40rpx;
  padding: 48rpx 20rpx 40rpx;
  text-align: center;
  transition: all 0.35s cubic-bezier(0.2, 0.9, 0.4, 1.2);
  border: 1rpx solid var(--card-border);
  box-shadow: 0 22rpx 50rpx rgba(59, 130, 246, 0.12);
  overflow: hidden;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(229, 242, 255, 0.98));
}

.card-fitness {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(96, 165, 250, 0.18));
}
.card-weightloss {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.16), rgba(56, 189, 248, 0.18));
}
.card-wellness {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.16), rgba(56, 189, 248, 0.18));
}
.card-work {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.16), rgba(20, 184, 166, 0.18));
}
.card-study {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(34, 197, 94, 0.18));
}

.menu-card .card-glow {
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

.card-title {
  font-size: 40rpx;
  font-weight: 800;
  display: block;
  margin-bottom: 12rpx;
  letter-spacing: -0.3rpx;
  color: var(--text-primary);
}

.card-fitness .card-title {
  color: var(--text-primary);
}
.card-weightloss .card-title {
  color: var(--text-primary);
}
.card-wellness .card-title {
  color: var(--text-primary);
}
.card-work .card-title {
  color: var(--text-primary);
}

.card-desc {
  font-size: 24rpx;
  font-weight: 600;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.65);
  display: inline-block;
  padding: 8rpx 22rpx;
  border-radius: 26rpx;
  backdrop-filter: blur(4rpx);
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
  gap: 16rpx;
  margin-top: 10rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.14), rgba(34, 197, 94, 0.12));
  backdrop-filter: blur(20rpx);
  padding: 26rpx 32rpx;
  border-radius: 36rpx;
  border: 1rpx solid var(--card-border);
  box-shadow: 0 20rpx 44rpx rgba(14, 165, 233, 0.14);
  transition: all 0.2s;
}
.settings-btn:active { transform: scale(0.92); background: rgba(0,0,0,0.08); }

/* 2x2 网格菜单 */
.menu-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28rpx;
}

.tip-text {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.5rpx;
  flex: 1;
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