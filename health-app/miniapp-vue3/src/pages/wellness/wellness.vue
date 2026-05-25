<template>
  <scroll-view class="wellness-container" scroll-y>
    <view class="inner-wrapper">
      <!-- 顶部装饰 -->
      <view class="hero-section">
        <text class="hero-icon">🌿</text>
        <text class="hero-title">智能养生顾问</text>
        <text class="hero-subtitle">为您定制个性化养生方案</text>
      </view>

      <!-- 节气养生卡片 -->
      <view class="solar-card" v-if="currentTerm">
        <view class="solar-header">
          <text class="solar-icon">{{ currentTerm.icon }}</text>
          <view class="solar-info">
            <text class="solar-name">{{ currentTerm.name }}</text>
            <text class="solar-date">{{ currentTerm.date }}</text>
          </view>
        </view>
        <text class="solar-tip">🌱 养生重点：{{ currentTerm.tip }}</text>
      </view>

      <!-- 信息收集表单 -->
      <view class="form-card">
        <!-- 年龄 - 同行布局 -->
        <view class="form-item form-item-row">
          <view class="label-with-icon">
            <text class="label-icon">📅</text>
            <text class="label">年龄</text>
            <text class="optional">(选填)</text>
          </view>
          <textarea 
            v-model="formData.age"
            placeholder="请输入年龄"
            class="custom-input inline-input"
            auto-height
          />
        </view>

        <view class="form-item">
          <view class="label-with-icon">
            <text class="label-icon">💊</text>
            <text class="label">慢性疾病/健康问题</text>
            <text class="optional">(可多选，以逗号分隔)</text>
          </view>
          <textarea 
            v-model="formData.diseases" 
            placeholder="例如: 高血压, 2型糖尿病, 关节炎" 
            placeholder-class="input-placeholder"
            class="custom-textarea"
            auto-height
          />
          <!-- 快速标签选择 -->
          <view class="quick-tags">
            <text class="tag-label">快速添加：</text>
            <view class="tags-wrapper">
              <text 
                v-for="tag in commonDiseases" 
                :key="tag"
                class="tag"
                @click="addDiseaseTag(tag)"
              >{{ tag }}</text>
            </view>
          </view>
        </view>

        <view class="form-item">
          <view class="label-with-icon">
            <text class="label-icon">📝</text>
            <text class="label">其他健康信息</text>
            <text class="optional">(选填)</text>
          </view>
          <textarea 
            v-model="formData.additionalInfo" 
            placeholder="例如: 经常失眠、膝盖疼痛、平时喜欢散步..." 
            placeholder-class="input-placeholder"
            class="custom-textarea"
            auto-height
          />
        </view>

        <button 
          class="submit-btn" 
          @click="getWellnessAdvice" 
          :disabled="isLoading"
        >
          <text v-if="!isLoading">✨ 获取养生建议 ✨</text>
          <text v-else class="loading-text">🔄 AI正在思考中...</text>
        </button>
      </view>

      <!-- ========== 养生打卡与成就系统 ========== -->
      <view class="checkin-card" v-if="isLoggedIn">
        <view class="checkin-header">
          <text class="checkin-title">📅 每日养生打卡</text>
          <text class="checkin-streak">🔥 连续打卡 {{ streakDays }} 天</text>
        </view>

        <!-- 今日任务列表 -->
        <view class="task-list">
          <view v-for="task in tasks" :key="task.id" class="task-item">
            <label class="task-checkbox">
              <checkbox :value="task.id" :checked="todayCheckin[task.id]" @click="toggleTask(task.id)" style="transform: scale(0.8);" />
              <text class="task-name">{{ task.name }}</text>
              <text class="task-target">{{ task.target }}</text>
            </label>
          </view>
        </view>

        <!-- 徽章展示 -->
        <view class="badge-section" v-if="badges.length">
          <text class="badge-label">🏅 成就徽章</text>
          <view class="badge-list">
            <view v-for="badge in badges" :key="badge.name" class="badge-item">
              <text class="badge-icon">{{ badge.icon }}</text>
              <text class="badge-name">{{ badge.name }}</text>
            </view>
          </view>
        </view>

        <!-- 月度报告入口 -->
        <button class="report-btn" @click="showMonthlyReport">📊 查看月度养生报告</button>
      </view>

      <!-- 建议展示区域 -->
      <view class="advice-card" v-if="adviceContent">
        <view class="advice-header">
          <text class="advice-icon">📖</text>
          <text class="advice-title">您的专属养生方案</text>
          <view class="copy-btn" @click="copyAdvice">
            <text>📋 复制</text>
          </view>
        </view>
        <view class="advice-content">
          <text class="advice-text">{{ adviceContent }}</text>
        </view>
        <view class="advice-footer">
          <text class="advice-note">* 本建议由AI生成，仅供参考，如有身体不适请及时就医</text>
        </view>
      </view>

      <!-- 加载骨架屏 -->
      <view class="loading-skeleton" v-if="isLoading">
        <view class="skeleton-header"></view>
        <view class="skeleton-line"></view>
        <view class="skeleton-line short"></view>
        <view class="skeleton-line"></view>
      </view>
    </view>
  </scroll-view>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useUserStore } from '@/store/user'
import { wellnessApi } from '@/utils/api'

const userStore = useUserStore()
const { isLoggedIn, state } = userStore

// 表单数据
const formData = ref({
  age: '',
  diseases: '',
  additionalInfo: ''
})

const isLoading = ref(false)
const adviceContent = ref('')
const currentTerm = ref(null)

// 常见疾病快速标签
const commonDiseases = [
  '高血压', '糖尿病', '高血脂', '冠心病', 
  '关节炎', '骨质疏松', '失眠', '消化不良'
]

// ========== 打卡系统（支持后端失败时使用本地模拟数据） ==========
const tasks = ref([
  { id: 'water', name: '喝水', target: '8杯', earlyBird: false },
  { id: 'footbath', name: '泡脚', target: '20分钟', earlyBird: false },
  { id: 'earlySleep', name: '早睡', target: '23:00前', earlyBird: true },
  { id: 'walk', name: '散步', target: '30分钟', earlyBird: false }
])

const todayCheckin = ref({})
const streakDays = ref(0)
const badges = ref([])

const username = computed(() => state.username || 'guest')

function getTodayStr() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// 从本地存储读取数据（模拟数据后备）
function loadFromLocalStorage() {
  const key = `checkin_${username.value}`
  const data = uni.getStorageSync(key) || {}
  const today = getTodayStr()
  if (data[today]) {
    todayCheckin.value = data[today].tasks || {}
  } else {
    todayCheckin.value = {}
  }
  streakDays.value = data.streakDays || 0
  loadBadgesFromLocal(data)
}

function loadBadgesFromLocal(data) {
  const newBadges = []
  const streak = data.streakDays || 0
  if (streak >= 7) newBadges.push({ name: '养生新手', icon: '🌱' })
  if (streak >= 30) newBadges.push({ name: '养生大师', icon: '🏆' })
  if (streak >= 100) newBadges.push({ name: '终极养生王', icon: '👑' })
  
  let earlySleepCount = 0
  for (const dayKey in data) {
    if (dayKey === 'streakDays' || dayKey === 'lastCheckinDate') continue
    const dayTasks = data[dayKey].tasks
    if (dayTasks && dayTasks.earlySleep === true) earlySleepCount++
  }
  if (earlySleepCount >= 14) {
    newBadges.push({ name: '早睡达人', icon: '🌙' })
  }
  badges.value = newBadges
}

// 从后端加载数据，失败则从本地加载
async function loadCheckinData() {
  if (!isLoggedIn.value) return
  try {
    // 获取今日打卡数据
    const res = await wellnessApi.getTodayCheckin()
    if (res && res.tasks) {
      todayCheckin.value = res.tasks
    } else {
      todayCheckin.value = {}
    }
    // 获取所有历史记录用于计算连续天数和徽章
    const historyRes = await wellnessApi.getAllCheckinHistory()
    if (historyRes && historyRes.checkins) {
      const checkins = historyRes.checkins
      // 计算连续打卡天数
      let streak = 0
      let currentDate = new Date()
      const checkinMap = {}
      checkins.forEach(item => {
        checkinMap[item.date] = item.tasks
      })
      while (true) {
        const dateStr = `${currentDate.getFullYear()}-${String(currentDate.getMonth()+1).padStart(2,'0')}-${String(currentDate.getDate()).padStart(2,'0')}`
        const dayTasks = checkinMap[dateStr]
        const hasCheckin = dayTasks && Object.values(dayTasks).some(v => v === true)
        if (hasCheckin) {
          streak++
          currentDate.setDate(currentDate.getDate() - 1)
        } else {
          break
        }
      }
      streakDays.value = streak
      // 加载徽章
      loadBadgesFromMap(checkinMap)
    } else {
      throw new Error('无历史记录')
    }
  } catch (error) {
    console.error('后端加载失败，使用本地数据', error)
    uni.showToast({ title: '后端连接失败，使用本地数据', icon: 'none', duration: 2000 })
    loadFromLocalStorage()
  }
}

function loadBadgesFromMap(checkinMap) {
  const newBadges = []
  // 计算最大连续打卡天数
  let maxStreak = 0
  let currentStreak = 0
  const dates = Object.keys(checkinMap).sort()
  let prevDate = null
  for (let dateStr of dates) {
    const tasks = checkinMap[dateStr]
    const hasCheckin = tasks && Object.values(tasks).some(v => v === true)
    if (hasCheckin) {
      if (prevDate) {
        const diff = (new Date(dateStr) - new Date(prevDate)) / (1000*60*60*24)
        if (diff === 1) {
          currentStreak++
        } else {
          currentStreak = 1
        }
      } else {
        currentStreak = 1
      }
      if (currentStreak > maxStreak) maxStreak = currentStreak
      prevDate = dateStr
    } else {
      currentStreak = 0
    }
  }
  if (maxStreak >= 7) newBadges.push({ name: '养生新手', icon: '🌱' })
  if (maxStreak >= 30) newBadges.push({ name: '养生大师', icon: '🏆' })
  if (maxStreak >= 100) newBadges.push({ name: '终极养生王', icon: '👑' })

  let earlySleepCount = 0
  for (const dateStr in checkinMap) {
    const tasks = checkinMap[dateStr]
    if (tasks && tasks.earlySleep === true) earlySleepCount++
  }
  if (earlySleepCount >= 14) {
    newBadges.push({ name: '早睡达人', icon: '🌙' })
  }
  badges.value = newBadges
}

// 保存打卡数据：优先后端，失败则存本地
async function saveCheckinData() {
  if (!isLoggedIn.value) return
  try {
    await wellnessApi.saveTodayCheckin(todayCheckin.value)
    // 保存成功后重新加载以更新连续天数和徽章
    await loadCheckinData()
    uni.showToast({ title: '保存成功', icon: 'success' })
  } catch (error) {
    console.error('后端保存失败，保存到本地', error)
    // 保存到本地存储
    const key = `checkin_${username.value}`
    const existing = uni.getStorageSync(key) || {}
    const today = getTodayStr()
    existing[today] = { tasks: todayCheckin.value, date: today }
    const hasAnyTask = Object.values(todayCheckin.value).some(v => v === true)
    if (hasAnyTask) {
      const lastDate = existing.lastCheckinDate
      const todayDate = new Date(today)
      if (lastDate) {
        const last = new Date(lastDate)
        const diffDays = Math.floor((todayDate - last) / (1000 * 60 * 60 * 24))
        if (diffDays === 1) {
          existing.streakDays = (existing.streakDays || 0) + 1
        } else if (diffDays > 1) {
          existing.streakDays = 1
        }
      } else {
        existing.streakDays = 1
      }
      existing.lastCheckinDate = today
    }
    uni.setStorageSync(key, existing)
    // 重新从本地加载以更新显示
    loadFromLocalStorage()
    uni.showToast({ title: '已保存到本地，网络恢复后同步', icon: 'none', duration: 2000 })
  }
}

function toggleTask(taskId) {
  if (!isLoggedIn.value) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  const current = todayCheckin.value[taskId] || false
  todayCheckin.value = { ...todayCheckin.value, [taskId]: !current }
  saveCheckinData()
}

function showMonthlyReport() {
  if (!isLoggedIn.value) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/pages/wellness/checkin-report' })
}

// ========== 节气系统 ==========
const solarTermsData = [
  { name: '立春', start: '2-3', end: '2-17', tip: '养肝护阳，防风御寒', icon: '🌱' },
  { name: '雨水', start: '2-18', end: '3-4', tip: '健脾祛湿，春捂保暖', icon: '💧' },
  { name: '惊蛰', start: '3-5', end: '3-19', tip: '顺肝助脾，预防流感', icon: '⚡' },
  { name: '春分', start: '3-20', end: '4-3', tip: '阴阳平衡，养肝健脾', icon: '🌗' },
  { name: '清明', start: '4-4', end: '4-19', tip: '养肝护胃，踏青散郁', icon: '🌧️' },
  { name: '谷雨', start: '4-20', end: '5-4', tip: '健脾祛湿，防过敏', icon: '🌾' },
  { name: '立夏', start: '5-5', end: '5-20', tip: '养心安神，清淡饮食', icon: '☀️' },
  { name: '小满', start: '5-21', end: '6-4', tip: '清热利湿，防皮肤病', icon: '🌾' },
  { name: '芒种', start: '6-5', end: '6-20', tip: '清热解暑，午间小憩', icon: '🌾' },
  { name: '夏至', start: '6-21', end: '7-6', tip: '养阳护心，防暑补水', icon: '☀️' },
  { name: '小暑', start: '7-7', end: '7-21', tip: '清热解暑，冬病夏治', icon: '🔥' },
  { name: '大暑', start: '7-22', end: '8-6', tip: '清热祛湿，养心健脾', icon: '🔥' },
  { name: '立秋', start: '8-7', end: '8-22', tip: '养肺润燥，少辛增酸', icon: '🍂' },
  { name: '处暑', start: '8-23', end: '9-6', tip: '滋阴润肺，早睡早起', icon: '🍂' },
  { name: '白露', start: '9-7', end: '9-21', tip: '防秋燥，护肺胃', icon: '💧' },
  { name: '秋分', start: '9-22', end: '10-7', tip: '阴阳平衡，润肺防寒', icon: '🌗' },
  { name: '寒露', start: '10-8', end: '10-22', tip: '养阴防燥，保暖足部', icon: '🍂' },
  { name: '霜降', start: '10-23', end: '11-6', tip: '健脾养胃，防寒保暖', icon: '❄️' },
  { name: '立冬', start: '11-7', end: '11-21', tip: '补肾藏精，温补防寒', icon: '⛄' },
  { name: '小雪', start: '11-22', end: '12-6', tip: '温肾养阳，清内火', icon: '❄️' },
  { name: '大雪', start: '12-7', end: '12-20', tip: '温补避寒，早睡晚起', icon: '❄️' },
  { name: '冬至', start: '12-21', end: '1-4', tip: '温补阳气，数九寒天', icon: '⛄' },
  { name: '小寒', start: '1-5', end: '1-19', tip: '温肾壮阳，防寒保暖', icon: '❄️' },
  { name: '大寒', start: '1-20', end: '2-2', tip: '冬藏转春生，固肾健脾', icon: '❄️' }
]

function getCurrentSolarTerm() {
  const getDayOfYear = (month, day) => {
    const daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let total = 0;
    for (let i = 0; i < month - 1; i++) total += daysInMonth[i];
    total += day;
    return total;
  };
  const now = new Date();
  const currentMonth = now.getMonth() + 1;
  const currentDay = now.getDate();
  let current = getDayOfYear(currentMonth, currentDay);
  const terms = solarTermsData.map(term => {
    let [sM, sD] = term.start.split('-').map(Number);
    let [eM, eD] = term.end.split('-').map(Number);
    let start = getDayOfYear(sM, sD);
    let end = getDayOfYear(eM, eD);
    if (end < start) end += 365;
    return { ...term, start, end, rawStart: term.start, rawEnd: term.end };
  });
  if (current < terms[0].start) current += 365;
  const found = terms.find(t => current >= t.start && current <= t.end);
  if (found) {
    return {
      name: found.name,
      tip: found.tip,
      icon: found.icon,
      date: `${found.rawStart} 至 ${found.rawEnd}`
    };
  }
  return null;
}

function checkAndNotifyTerm() {
  const term = currentTerm.value
  if (!term) return
  const lastTerm = uni.getStorageSync('last_notified_term')
  if (lastTerm !== term.name) {
    uni.showModal({
      title: '🌿 节气提醒',
      content: `今日是「${term.name}」，${term.tip}。请注意节气养生。`,
      confirmText: '知道了',
      showCancel: false
    })
    uni.setStorageSync('last_notified_term', term.name)
  }
}

// 原有方法
const addDiseaseTag = (tag) => {
  let current = formData.value.diseases
  let diseasesList = current ? current.split(/[，,]+/).map(s => s.trim()) : []
  if (!diseasesList.includes(tag)) {
    diseasesList.push(tag)
    formData.value.diseases = diseasesList.join('、')
  } else {
    uni.showToast({ title: '该疾病已添加', icon: 'none', duration: 1500 })
  }
}

const getWellnessAdvice = async () => {
  if (!isLoggedIn.value) {
    uni.showModal({
      title: '提示',
      content: '请先登录后再使用养生功能',
      success: (res) => {
        if (res.confirm) uni.switchTab({ url: '/pages/index/index' })
      }
    })
    return
  }
  if (formData.value.age && (formData.value.age < 0 || formData.value.age > 120)) {
    uni.showToast({ title: '请输入有效的年龄（1-120岁）', icon: 'none' })
    return
  }
  isLoading.value = true
  adviceContent.value = ''
  try {
    const params = {
      age: formData.value.age ? parseInt(formData.value.age) : null,
      diseases: formData.value.diseases || '无特殊疾病',
      additionalInfo: formData.value.additionalInfo || '无其他补充信息'
    }
    const res = await wellnessApi.getAdvice(params)
    if (res && res.advice) {
      adviceContent.value = res.advice
      setTimeout(() => {
        uni.pageScrollTo({ selector: '.advice-card', duration: 300 })
      }, 100)
    } else {
      throw new Error('获取建议失败')
    }
  } catch (error) {
    console.error('获取养生建议失败:', error)
    uni.showToast({ 
      title: error.message || '服务繁忙，请稍后再试', 
      icon: 'none',
      duration: 2000
    })
  } finally {
    isLoading.value = false
  }
}

const copyAdvice = () => {
  if (!adviceContent.value) return
  uni.setClipboardData({
    data: adviceContent.value,
    success: () => uni.showToast({ title: '复制成功', icon: 'success' }),
    fail: () => uni.showToast({ title: '复制失败', icon: 'none' })
  })
}

onMounted(() => {
  if (!isLoggedIn.value) {
    uni.showModal({
      title: '提示',
      content: '请先登录使用养生功能',
      showCancel: false,
      success: () => uni.switchTab({ url: '/pages/index/index' })
    })
  } else {
    currentTerm.value = getCurrentSolarTerm()
    if (currentTerm.value) checkAndNotifyTerm()
    loadCheckinData()
  }
})
</script>

<style scoped>
/* 外层滚动容器 - 保证无横向滚动 */
.wellness-container {
  width: 100%;
  height: 100vh;
  overflow-x: hidden;
  background: linear-gradient(180deg, #f0f9f0 0%, #e8f5e9 100%);
  box-sizing: border-box;
}

/* 内部内容容器，统一左右内边距，确保左右对称 */
.inner-wrapper {
  padding: 20rpx 30rpx 40rpx 30rpx;
  box-sizing: border-box;
  width: 100%;
}

/* 头部区域 */
.hero-section {
  display: block;
  text-align: center;
  padding: 40rpx 30rpx 30rpx;
  background: linear-gradient(135deg, #a5d6a7 0%, #c8e6c9 100%);
  border-radius: 60rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 12rpx 24rpx rgba(0, 0, 0, 0.08);
  box-sizing: border-box;
}

.hero-icon {
  font-size: 80rpx;
  display: block;
  margin-bottom: 16rpx;
}

.hero-title {
  font-size: 44rpx;
  font-weight: 800;
  color: #2e7d32;
  letter-spacing: 2rpx;
  display: block;
  width: 100%;
  text-align: center;
  margin-bottom: 12rpx;
}

.hero-subtitle {
  font-size: 26rpx;
  color: #558b2f;
  font-weight: 500;
  display: block;
  width: 100%;
  text-align: center;
  margin-top: 0;
}

/* 节气卡片 */
.solar-card {
  background: linear-gradient(135deg, #fff8e7, #fff3e0);
  border-radius: 48rpx;
  padding: 30rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 8rpx 20rpx rgba(0, 0, 0, 0.05);
  border: 1px solid #ffe5b4;
}
.solar-header {
  display: flex;
  align-items: center;
  margin-bottom: 20rpx;
}
.solar-icon {
  font-size: 64rpx;
  margin-right: 20rpx;
}
.solar-info {
  flex: 1;
}
.solar-name {
  font-size: 40rpx;
  font-weight: 800;
  color: #c27e2a;
  display: block;
}
.solar-date {
  font-size: 26rpx;
  color: #ad8b5e;
}
.solar-tip {
  font-size: 30rpx;
  color: #5c3d1a;
  line-height: 1.5;
  display: block;
  background: rgba(255,245,220,0.8);
  padding: 20rpx;
  border-radius: 32rpx;
}

/* 表单卡片 */
.form-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 48rpx;
  padding: 40rpx 32rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 8rpx 20rpx rgba(0, 0, 0, 0.05);
  box-sizing: border-box;
  width: 100%;
}

.form-item {
  margin-bottom: 40rpx;
  width: 100%;
}

.form-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16rpx;
}
.form-item-row .label-with-icon {
  flex-shrink: 0;
  margin-bottom: 0;
  width: auto;
}
.form-item-row .inline-input {
  flex: 1;
  min-width: 240rpx;
  margin-bottom: 0;
}

.label-with-icon {
  margin-bottom: 16rpx;
  display: flex;
  align-items: baseline;
}

.label-icon {
  font-size: 32rpx;
  margin-right: 12rpx;
}

.label {
  font-size: 32rpx;
  font-weight: 700;
  color: #2c3e2f;
  margin-right: 12rpx;
}

.optional {
  font-size: 24rpx;
  color: #8d9e8d;
}

.custom-input,
.custom-textarea {
  width: 100%;
  padding: 24rpx 28rpx;
  background: #f5f9f5;
  border-radius: 32rpx;
  font-size: 30rpx;
  border: 2rpx solid #d0e2d0;
  transition: all 0.2s;
  box-sizing: border-box;
  color: #1b3b1a;
}

.custom-input:focus,
.custom-textarea:focus {
  border-color: #66bb6a;
  background: #ffffff;
  box-shadow: 0 0 0 6rpx rgba(102, 187, 106, 0.1);
}

.custom-textarea {
  min-height: 140rpx;
}

.quick-tags {
  margin-top: 20rpx;
  width: 100%;
}

.tag-label {
  font-size: 26rpx;
  color: #5d7a5c;
  margin-right: 16rpx;
  display: inline-block;
}

.tags-wrapper {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 16rpx;
  width: calc(100% - 120rpx);
}

.tag {
  background: #e8f5e9;
  padding: 12rpx 24rpx;
  border-radius: 48rpx;
  font-size: 26rpx;
  color: #2e7d32;
  font-weight: 500;
  transition: all 0.2s;
  border: 1px solid #c8e6c9;
}

.tag:active {
  background: #c8e6c9;
  transform: scale(0.96);
}

.submit-btn {
  background: linear-gradient(135deg, #43a047 0%, #2e7d32 100%);
  color: white;
  border-radius: 60rpx;
  height: 100rpx;
  line-height: 100rpx;
  font-size: 34rpx;
  font-weight: 700;
  box-shadow: 0 16rpx 28rpx -10rpx rgba(46, 125, 50, 0.4);
  margin-top: 20rpx;
  transition: all 0.2s;
  width: 100%;
  box-sizing: border-box;
  border: none;
}

.submit-btn:active {
  transform: scale(0.98);
  box-shadow: 0 8rpx 16rpx -6rpx rgba(46, 125, 50, 0.5);
}

.advice-card {
  background: #ffffff;
  border-radius: 48rpx;
  padding: 40rpx 32rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 20rpx 40rpx rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(102, 187, 106, 0.3);
  animation: slideUp 0.4s ease-out;
  box-sizing: border-box;
  width: 100%;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(40rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.advice-header {
  display: flex;
  align-items: center;
  margin-bottom: 32rpx;
  padding-bottom: 20rpx;
  border-bottom: 2rpx solid #e8f5e9;
  width: 100%;
}

.advice-icon {
  font-size: 48rpx;
  margin-right: 16rpx;
}

.advice-title {
  flex: 1;
  font-size: 36rpx;
  font-weight: 800;
  background: linear-gradient(135deg, #2e7d32, #66bb6a);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.copy-btn {
  background: #f1f8e9;
  padding: 12rpx 24rpx;
  border-radius: 40rpx;
  font-size: 26rpx;
  color: #558b2f;
  font-weight: 600;
}

.advice-content {
  background: #fafdfa;
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  width: 100%;
  box-sizing: border-box;
}

.advice-text {
  font-size: 30rpx;
  line-height: 1.8;
  color: #2c3e2f;
  white-space: pre-wrap;
  word-break: break-word;
}

.advice-footer {
  text-align: center;
}

.advice-note {
  font-size: 22rpx;
  color: #9eaf9e;
}

.empty-state {
  text-align: center;
  padding: 100rpx 40rpx;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 48rpx;
  width: 100%;
  box-sizing: border-box;
}

.empty-icon {
  font-size: 100rpx;
  display: block;
  margin-bottom: 24rpx;
  opacity: 0.6;
}

.empty-text {
  font-size: 32rpx;
  color: #5c7a5c;
  font-weight: 600;
  display: block;
  margin-bottom: 12rpx;
}

.empty-sub {
  font-size: 26rpx;
  color: #8ba88b;
}

.loading-skeleton {
  background: #ffffff;
  border-radius: 48rpx;
  padding: 40rpx;
  width: 100%;
  box-sizing: border-box;
}

.skeleton-header {
  width: 60%;
  height: 40rpx;
  background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%);
  background-size: 200% 100%;
  animation: loading 1.5s infinite;
  border-radius: 8rpx;
  margin-bottom: 32rpx;
}

.skeleton-line {
  height: 32rpx;
  background: linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%);
  background-size: 200% 100%;
  animation: loading 1.5s infinite;
  border-radius: 8rpx;
  margin-bottom: 24rpx;
}

.skeleton-line.short {
  width: 80%;
}

@keyframes loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.input-placeholder {
  color: #bcd0bc;
  font-size: 28rpx;
  white-space: nowrap;
  overflow: visible;
}

.wellness-container ::-webkit-scrollbar {
  width: 0;
  height: 0;
  background: transparent;
}

/* ========== 新增打卡与成就系统样式 ========== */
.checkin-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 48rpx;
  padding: 30rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 8rpx 20rpx rgba(0, 0, 0, 0.05);
  border: 1px solid #d0e2d0;
}
.checkin-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 20rpx;
  padding-bottom: 16rpx;
  border-bottom: 2rpx solid #e8f5e9;
}
.checkin-title {
  font-size: 36rpx;
  font-weight: 800;
  color: #2e7d32;
}
.checkin-streak {
  font-size: 28rpx;
  color: #ef6c00;
  background: #fff3e0;
  padding: 8rpx 20rpx;
  border-radius: 60rpx;
}
.task-list {
  margin: 20rpx 0;
}
.task-item {
  padding: 16rpx 0;
  border-bottom: 1px solid #e8f5e9;
}
.task-checkbox {
  display: flex;
  align-items: center;
}
.task-name {
  font-size: 30rpx;
  font-weight: 600;
  margin-left: 16rpx;
  flex: 1;
  color: #2c3e2f;
}
.task-target {
  font-size: 26rpx;
  color: #8d9e8d;
}
.badge-section {
  margin: 20rpx 0;
  background: #fef9ef;
  border-radius: 32rpx;
  padding: 20rpx;
}
.badge-label {
  font-size: 28rpx;
  font-weight: 700;
  color: #bf6f00;
  display: block;
  margin-bottom: 12rpx;
}
.badge-list {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.badge-item {
  background: white;
  border-radius: 60rpx;
  padding: 8rpx 24rpx;
  display: inline-flex;
  align-items: center;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.05);
}
.badge-icon {
  font-size: 32rpx;
  margin-right: 8rpx;
}
.badge-name {
  font-size: 26rpx;
  font-weight: 600;
  color: #c27e2a;
}
.report-btn {
  background: linear-gradient(135deg, #66bb6a, #43a047);
  color: white;
  border-radius: 60rpx;
  height: 80rpx;
  line-height: 80rpx;
  font-size: 30rpx;
  font-weight: 600;
  margin-top: 20rpx;
  border: none;
}
.report-btn:active {       
  transform: scale(0.98);
}
</style>