<template>
  <scroll-view class="work-container" scroll-y>
    <view class="inner-wrapper">
      <!-- 顶部职业栏 -->
      <view class="greeting-card">
        <text class="greeting-icon">{{ currentOccupationIcon }}</text>
        <text class="greeting-text">身份：{{ currentOccupationDisplay }}</text>
        <text class="change-occupation" @click="goToOccupationSelect">更换职业</text>
      </view>

      <!-- 今日工作时长 -->
      <view class="duration-card">
        <text class="card-title">⏱️ 今日工作时长</text>
        <text class="duration-value">{{ formattedWorkDuration }}</text>
        <text class="duration-note">从后端获取并展示今日累计工作时间</text>
      </view>

      <!-- 今日 TODO -->
      <view class="todo-card">
        <text class="card-title">📝 今日 TODO</text>
        <view class="todo-input-row">
          <input class="todo-input" v-model="newTodoText" placeholder="添加新的今日任务" placeholder-class="placeholder" />
          <button class="add-todo-btn" @click="addTodo">添加</button>
        </view>
        <view class="todo-list">
          <view v-for="todo in todoList" :key="todo.id" class="todo-item">
            <text class="todo-text">{{ todo.content }}</text>
            <button class="todo-complete-btn" @click="completeTodo(todo.id)">完成</button>
          </view>
          <text v-if="todoList.length === 0" class="todo-empty">暂无今日TODO，赶紧添加一条吧！</text>
        </view>
      </view>

      <!-- 番茄钟入口卡片 -->
      <view class="pomodoro-entry-card">
        <text class="card-title">🍅 番茄钟</text>
        <text class="pomodoro-entry-desc">跳转到专属番茄钟页面进行专注计时，开始你的高效工作节奏。</text>
        <button class="pomodoro-open-btn" @click="goToPomodoro">打开番茄钟</button>
      </view>

      <!-- 久坐提醒卡片 -->
      <view class="reminder-card">
        <view class="reminder-header">
          <text class="card-title">🪑 久坐提醒</text>
          <switch :checked="sedentaryEnabled" @change="toggleSedentary" color="#43a047" />
        </view>
        <view class="reminder-item" v-if="sedentaryEnabled">
          <text>提醒间隔（分钟）</text>
          <input 
            type="number" 
            v-model="sedentaryIntervalInput" 
            @blur="updateSedentaryInterval"
            class="interval-input"
          />
          <text class="unit">分钟</text>
        </view>
      </view>

      <!-- 职业专属健康卡片 -->
      <view class="career-card">
        <text class="card-title">{{ careerCardTitle }}</text>
        <text class="card-subtitle">{{ careerCardSubtitle }}</text>

        <!-- IT/设计 -->
        <view v-if="currentOccupation === 'it'" class="career-content">
          <view class="health-metric">
            <text class="metric-label">👋 手腕健康指数</text>
            <text class="metric-value">{{ wristHealthScore }}%</text>
            <button class="action-btn" @click="recordWristExercise">记录手腕操</button>
          </view>
          <view class="health-metric">
            <text class="metric-label">👀 今日护眼次数</text>
            <text class="metric-value">{{ eyeRestCount }} 次</text>
            <button class="action-btn" @click="recordEyeRest">完成20-20-20</button>
          </view>
        </view>

        <!-- 教师 -->
        <view v-if="currentOccupation === 'teacher'" class="career-content">
          <view class="health-metric">
            <text class="metric-label">💧 今日饮水量</text>
            <text class="metric-value">{{ waterIntake }} 杯</text>
            <button class="action-btn" @click="addWater">+1杯</button>
          </view>
          <view class="health-metric">
            <text class="metric-label">🎤 声带休息次数</text>
            <text class="metric-value">{{ vocalRestCount }} 次</text>
            <button class="action-btn" @click="recordVocalRest">完成休息</button>
          </view>
        </view>

        <!-- 司机 -->
        <view v-if="currentOccupation === 'driver'" class="career-content">
          <view class="health-metric">
            <text class="metric-label">🦴 腰部放松次数</text>
            <text class="metric-value">{{ backRelaxCount }} 次</text>
            <button class="action-btn" @click="recordBackRelax">完成腰部操</button>
          </view>
          <view class="health-metric">
            <text class="metric-label">🅿️ 停车活动次数</text>
            <text class="metric-value">{{ stopMoveCount }} 次</text>
            <button class="action-btn" @click="recordStopMove">记录停车活动</button>
          </view>
        </view>

        <!-- 学生 -->
        <view v-if="currentOccupation === 'student'" class="career-content">
          <view class="health-metric">
            <text class="metric-label">👁️ 眼保健操次数</text>
            <text class="metric-value">{{ eyeExerciseCount }} 次</text>
            <button class="action-btn" @click="recordEyeExercise">完成眼操</button>
          </view>
          <view class="health-metric">
            <text class="metric-label">🏃 课间活动次数</text>
            <text class="metric-value">{{ classBreakCount }} 次</text>
            <button class="action-btn" @click="recordClassBreak">站立活动</button>
          </view>
        </view>

        <!-- 医疗 -->
        <view v-if="currentOccupation === 'medical'" class="career-content">
          <view class="health-metric">
            <text class="metric-label">🌬️ 深呼吸放松次数</text>
            <text class="metric-value">{{ deepBreathCount }} 次</text>
            <button class="action-btn" @click="recordDeepBreath">完成深呼吸</button>
          </view>
          <view class="health-metric">
            <text class="metric-label">🦵 腿部活动次数</text>
            <text class="metric-value">{{ legMoveCount }} 次</text>
            <button class="action-btn" @click="recordLegMove">勾脚尖/踮脚</button>
          </view>
        </view>

        <!-- 行政/文员 -->
        <view v-if="currentOccupation === 'admin'" class="career-content">
          <view class="health-metric">
            <text class="metric-label">💆 肩颈放松次数</text>
            <text class="metric-value">{{ neckRelaxCount }} 次</text>
            <button class="action-btn" @click="recordNeckRelax">完成肩颈操</button>
          </view>
          <view class="health-metric">
            <text class="metric-label">💧 今日饮水量</text>
            <text class="metric-value">{{ waterIntake }} 杯</text>
            <button class="action-btn" @click="addWater">+1杯</button>
          </view>
        </view>

        <!-- 销售/外勤 -->
        <view v-if="currentOccupation === 'sales'" class="career-content">
          <view class="health-metric">
            <text class="metric-label">🚶 今日步数</text>
            <text class="metric-value">{{ stepCount }} 步</text>
            <button class="action-btn" @click="syncStepCount">同步微信运动</button>
          </view>
          <view class="health-metric">
            <text class="metric-label">⚡ 能量补充次数</text>
            <text class="metric-value">{{ energySnackCount }} 次</text>
            <button class="action-btn" @click="recordEnergySnack">小食/饮水</button>
          </view>
        </view>

        <!-- 通用 -->
        <view v-if="currentOccupation === 'general'" class="career-content">
          <view class="health-metric">
            <text class="metric-label">🚶 站立活动次数</text>
            <text class="metric-value">{{ standCount }} 次</text>
            <button class="action-btn" @click="recordStand">站起来</button>
          </view>
          <view class="health-metric">
            <text class="metric-label">💧 今日饮水量</text>
            <text class="metric-value">{{ waterIntake }} 杯</text>
            <button class="action-btn" @click="addWater">+1杯</button>
          </view>
        </view>
      </view>

      <!-- 工作统计 -->
      <view class="stats-card">
        <text class="card-title">📊 工作统计</text>
        <view class="stats-grid">
          <view class="stat-item">
            <text class="stat-value">{{ todayFocusMinutes }}</text>
            <text class="stat-label">专注分钟</text>
          </view>
          <view class="stat-item">
            <text class="stat-value">{{ todaySessions }}</text>
            <text class="stat-label">番茄钟</text>
          </view>
          <view class="stat-item">
            <text class="stat-value">{{ careerExtraStat }}</text>
            <text class="stat-label">{{ extraStatLabel }}</text>
          </view>
        </view>
        <view class="weekly-trend" v-if="weeklyStats.length">
          <text class="trend-title">本周专注趋势</text>
          <view class="trend-bars">
            <view v-for="(item, idx) in weeklyStats" :key="idx" class="bar-item">
              <view class="bar" :style="{ height: item.height + 'rpx' }"></view>
              <text class="bar-label">{{ item.day }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 推荐微运动 -->
      <view class="exercises-card">
        <text class="card-title">🧘 今日推荐微运动</text>
        <view class="exercise-list">
          <view v-for="ex in recommendedExercises" :key="ex.id" class="exercise-item" @click="viewExerciseDetail(ex)">
            <text class="exercise-icon">{{ ex.icon }}</text>
            <view class="exercise-info">
              <text class="exercise-name">{{ ex.name }}</text>
              <text class="exercise-desc">{{ ex.shortDesc }}</text>
            </view>
            <text class="exercise-arrow">›</text>
          </view>
        </view>
      </view>
    </view>
  </scroll-view>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useUserStore } from '@/store/user'
import { workApi } from '@/utils/api'

const userStore = useUserStore()
const { isLoggedIn, state } = userStore

// 职业配置
const occupations = [
  { value: 'it', label: 'IT/设计', icon: '💻' },
  { value: 'teacher', label: '教育/培训', icon: '📚' },
  { value: 'driver', label: '司机/物流', icon: '🚚' },
  { value: 'student', label: '学生', icon: '🎓' },
  { value: 'medical', label: '医疗/护理', icon: '🏥' },
  { value: 'admin', label: '行政/文员', icon: '📄' },
  { value: 'sales', label: '销售/外勤', icon: '🤝' },
  { value: 'general', label: '通用', icon: '🌟' }
]

const currentOccupation = ref('general')
const currentOccupationLabel = computed(() => occupations.find(o => o.value === currentOccupation.value)?.label || '通用')
const currentOccupationDisplay = computed(() => {
  const map = {
    it: '精益求精的程序员',
    teacher: '教书育人的老师',
    driver: '一路护航的司机',
    student: '勤奋好学的学生',
    medical: '温柔有爱的医护人员',
    admin: '细心负责的文员',
    sales: '朝气蓬勃的销售达人',
    general: '元气满满的你'
  }
  return map[currentOccupation.value] || '超级棒的朋友'
})
const currentOccupationIcon = computed(() => occupations.find(o => o.value === currentOccupation.value)?.icon || '🌟')
const formattedWorkDuration = computed(() => {
  const minutes = todayWorkDuration.value || 0
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (hours > 0) {
    return `${hours}小时${mins}分钟`
  }
  return `${mins}分钟`
})

// 番茄钟
const WORK_DURATION = 25 * 60
const BREAK_DURATION = 5 * 60
let timerInterval = null
const isWorking = ref(true)
const remainingSeconds = ref(WORK_DURATION)
const isTimerRunning = ref(false)
let currentSessionId = null
const todayPomodoros = ref(0)
const todayFocusMinutes = ref(0)
const todaySessions = ref(0)
const todayWorkDuration = ref(0)
const todoList = ref([])
const newTodoText = ref('')

// 久坐提醒
const sedentaryEnabled = ref(true)
const sedentaryInterval = ref(45)
const sedentaryIntervalInput = ref('45')
let sedentaryTimer = null

// 职业专属数据
const wristHealthScore = ref(0)
const eyeRestCount = ref(0)
const waterIntake = ref(0)
const vocalRestCount = ref(0)
const backRelaxCount = ref(0)
const stopMoveCount = ref(0)
const eyeExerciseCount = ref(0)
const classBreakCount = ref(0)
const deepBreathCount = ref(0)
const legMoveCount = ref(0)
const neckRelaxCount = ref(0)
const stepCount = ref(0)
const energySnackCount = ref(0)
const standCount = ref(0)

// 统计
const weeklyStats = ref([])
const recommendedExercises = ref([])

// 额外统计标签
const extraStatLabel = computed(() => {
  const map = {
    it: '手腕健康', teacher: '饮水量(杯)', driver: '腰部放松',
    student: '眼操次数', medical: '深呼吸', admin: '肩颈放松',
    sales: '步数', general: '站立次数'
  }
  return map[currentOccupation.value] || '健康行动'
})
const careerExtraStat = computed(() => {
  const map = {
    it: wristHealthScore.value + '%',
    teacher: waterIntake.value,
    driver: backRelaxCount.value,
    student: eyeExerciseCount.value,
    medical: deepBreathCount.value,
    admin: neckRelaxCount.value,
    sales: stepCount.value,
    general: standCount.value
  }
  return map[currentOccupation.value] ?? 0
})

const careerCardTitle = computed(() => {
  const titles = {
    it: '💻 程序员专属健康', teacher: '📚 教师健康站', driver: '🚚 司机健康站',
    student: '🎓 学生健康站', medical: '🏥 医护健康站', admin: '📄 办公健康站',
    sales: '🤝 外勤健康站', general: '🌟 通用健康站'
  }
  return titles[currentOccupation.value] || '职业健康计划'
})
const careerCardSubtitle = computed(() => {
  const subs = {
    it: '保护手腕与眼睛', teacher: '多喝水，护嗓音', driver: '放松腰背，多活动',
    student: '护眼课间动起来', medical: '深呼吸，放松腿脚', admin: '肩颈舒展',
    sales: '走走更健康', general: '动起来更健康'
  }
  return subs[currentOccupation.value] || '坚持每日小行动'
})

// 辅助函数：加载所有数据
const loadAllData = async () => {
  try {
    // 1. 加载用户工作设置
    const settings = await workApi.getSettings()
    if (settings) {
      if (settings.occupation) currentOccupation.value = settings.occupation
      if (typeof settings.sedentaryEnabled === 'boolean') sedentaryEnabled.value = settings.sedentaryEnabled
      if (settings.sedentaryInterval) {
        sedentaryInterval.value = settings.sedentaryInterval
        sedentaryIntervalInput.value = String(settings.sedentaryInterval)
      }
    }
    
    // 2. 加载今日统计数据
    const todayStats = await workApi.getTodayStats()
    if (todayStats) {
      todayFocusMinutes.value = Number(todayStats.focusMinutes) || 0
      todaySessions.value = Number(todayStats.sessions) || 0
      todayPomodoros.value = Number(todayStats.sessions) || 0
    }

    // 2.1 加载今日工作时长
    await loadTodayWorkDuration()

    // 2.2 加载今日 TODO
    await loadTodayTodos()
    
    // 3. 加载本周趋势
    const weeklyData = await workApi.getWeeklyStats()
    if (weeklyData && weeklyData.length) {
      // 后端返回格式: [{ day: '一', minutes: 120 }, ...]
      const maxMinutes = Math.max(...weeklyData.map(d => d.minutes), 1)
      weeklyStats.value = weeklyData.map(day => ({
        day: day.day,
        minutes: day.minutes,
        height: Math.max(20, (day.minutes / maxMinutes) * 180)
      }))
    } else {
      // 模拟默认数据
      weeklyStats.value = [
        { day: '一', minutes: 120, height: 80 },
        { day: '二', minutes: 90, height: 60 },
        { day: '三', minutes: 150, height: 100 },
        { day: '四', minutes: 80, height: 53 },
        { day: '五', minutes: 110, height: 73 },
        { day: '六', minutes: 60, height: 40 },
        { day: '日', minutes: 0, height: 20 }
      ]
    }
    
    // 4. 加载职业健康数据
    await loadCareerHealthData()
    
    // 5. 加载推荐微运动
    const exercisesRes = await workApi.getRecommendedExercises(currentOccupation.value)
    const exercises = Array.isArray(exercisesRes) ? exercisesRes : (exercisesRes?.data || [])
    if (exercises.length) {
      recommendedExercises.value = exercises.map(ex => ({
        ...ex,
        detailUrl: ex.detailUrl || `/pages/work/exercise-detail?id=${ex.id}`
      }))
    } else {
      // 使用默认本地数据作为fallback
      recommendedExercises.value = getLocalRecommendedExercises(currentOccupation.value)
    }
    
    // 6. 启动久坐提醒
    if (sedentaryEnabled.value) startSedentaryReminder()
  } catch (error) {
    console.error('加载数据失败', error)
    uni.showToast({ title: '加载数据失败', icon: 'none' })
  }
}

// 加载职业健康数据
const loadCareerHealthData = async () => {
  try {
    const healthData = await workApi.getHealthData(currentOccupation.value)
    if (healthData) {
      wristHealthScore.value = healthData.wristHealthScore || 0
      eyeRestCount.value = healthData.eyeRestCount || 0
      waterIntake.value = healthData.waterIntake || 0
      vocalRestCount.value = healthData.vocalRestCount || 0
      backRelaxCount.value = healthData.backRelaxCount || 0
      stopMoveCount.value = healthData.stopMoveCount || 0
      eyeExerciseCount.value = healthData.eyeExerciseCount || 0
      classBreakCount.value = healthData.classBreakCount || 0
      deepBreathCount.value = healthData.deepBreathCount || 0
      legMoveCount.value = healthData.legMoveCount || 0
      neckRelaxCount.value = healthData.neckRelaxCount || 0
      stepCount.value = healthData.stepCount || 0
      energySnackCount.value = healthData.energySnackCount || 0
      standCount.value = healthData.standCount || 0
    }
  } catch (error) {
    console.error('加载职业健康数据失败', error)
  }
}

const loadTodayWorkDuration = async () => {
  try {
    const duration = await workApi.getTodayWorkDuration()
    todayWorkDuration.value = duration?.durationMinutes ?? duration?.workDuration ?? 0
  } catch (error) {
    console.warn('加载今日工作时长失败', error)
    todayWorkDuration.value = 0
  }
}

const loadTodayTodos = async () => {
  try {
    const todos = await workApi.getTodayTodos()
    if (Array.isArray(todos)) {
      todoList.value = todos.map(item => ({ id: item.id, content: item.content || item.title || '' }))
    } else if (todos?.data && Array.isArray(todos.data)) {
      todoList.value = todos.data.map(item => ({ id: item.id, content: item.content || item.title || '' }))
    } else {
      todoList.value = []
    }
  } catch (error) {
    console.warn('加载今日TODO失败', error)
    todoList.value = []
  }
}

const addTodo = async () => {
  const content = newTodoText.value.trim()
  if (!content) {
    uni.showToast({ title: '请输入待办内容', icon: 'none' })
    return
  }
  try {
    const result = await workApi.addTodayTodo(content)
    const newItem = result?.data || result || {}
    const todo = {
      id: newItem.id ?? Date.now(),
      content: newItem.content || newItem.title || content
    }
    todoList.value.unshift(todo)
    newTodoText.value = ''
    uni.showToast({ title: '添加成功', icon: 'success' })
  } catch (error) {
    console.warn('添加TODO失败，使用本地暂存', error)
    const todo = { id: Date.now(), content }
    todoList.value.unshift(todo)
    newTodoText.value = ''
    uni.showToast({ title: '已添加到本地', icon: 'none' })
  }
}

const completeTodo = async (id) => {
  try {
    await workApi.completeTodo(id)
    todoList.value = todoList.value.filter(item => item.id !== id)
    uni.showToast({ title: '已完成', icon: 'success' })
  } catch (error) {
    console.warn('完成TODO失败，仍从页面移除', error)
    todoList.value = todoList.value.filter(item => item.id !== id)
    uni.showToast({ title: '已标记完成', icon: 'success' })
  }
}

// 保存单个健康指标（通用方法）
const updateHealthMetric = async (metricName, increment = 1) => {
  try {
    const result = await workApi.updateHealthMetric({
      occupation: currentOccupation.value,
      metricName,
      increment
    })
    if (result && result.newValue !== undefined) {
      // 根据指标名更新对应的ref
      switch (metricName) {
        case 'wristHealthScore': wristHealthScore.value = result.newValue; break
        case 'eyeRestCount': eyeRestCount.value = result.newValue; break
        case 'waterIntake': waterIntake.value = result.newValue; break
        case 'vocalRestCount': vocalRestCount.value = result.newValue; break
        case 'backRelaxCount': backRelaxCount.value = result.newValue; break
        case 'stopMoveCount': stopMoveCount.value = result.newValue; break
        case 'eyeExerciseCount': eyeExerciseCount.value = result.newValue; break
        case 'classBreakCount': classBreakCount.value = result.newValue; break
        case 'deepBreathCount': deepBreathCount.value = result.newValue; break
        case 'legMoveCount': legMoveCount.value = result.newValue; break
        case 'neckRelaxCount': neckRelaxCount.value = result.newValue; break
        case 'stepCount': stepCount.value = result.newValue; break
        case 'energySnackCount': energySnackCount.value = result.newValue; break
        case 'standCount': standCount.value = result.newValue; break
      }
    } else {
      // 如果后端未返回新值，重新加载全部健康数据
      await loadCareerHealthData()
    }
    return true
  } catch (error) {
    console.error(`更新${metricName}失败`, error)
    uni.showToast({ title: '操作失败', icon: 'none' })
    return false
  }
}

// 打卡方法（调用后端接口）
const recordWristExercise = async () => {
  await updateHealthMetric('wristHealthScore', 10)
  uni.showToast({ title: '手腕操+1', icon: 'success' })
}
const recordEyeRest = async () => {
  await updateHealthMetric('eyeRestCount', 1)
  uni.showToast({ title: '眼睛休息啦', icon: 'success' })
}
const addWater = async () => {
  await updateHealthMetric('waterIntake', 1)
  uni.showToast({ title: '喝水+1杯', icon: 'success' })
}
const recordVocalRest = async () => {
  await updateHealthMetric('vocalRestCount', 1)
  uni.showToast({ title: '声带休息', icon: 'success' })
}
const recordBackRelax = async () => {
  await updateHealthMetric('backRelaxCount', 1)
  uni.showToast({ title: '腰部放松', icon: 'success' })
}
const recordStopMove = async () => {
  await updateHealthMetric('stopMoveCount', 1)
  uni.showToast({ title: '停车活动', icon: 'success' })
}
const recordEyeExercise = async () => {
  await updateHealthMetric('eyeExerciseCount', 1)
  uni.showToast({ title: '眼保健操+1', icon: 'success' })
}
const recordClassBreak = async () => {
  await updateHealthMetric('classBreakCount', 1)
  uni.showToast({ title: '课间活动', icon: 'success' })
}
const recordDeepBreath = async () => {
  await updateHealthMetric('deepBreathCount', 1)
  uni.showToast({ title: '深呼吸', icon: 'success' })
}
const recordLegMove = async () => {
  await updateHealthMetric('legMoveCount', 1)
  uni.showToast({ title: '腿部活动', icon: 'success' })
}
const recordNeckRelax = async () => {
  await updateHealthMetric('neckRelaxCount', 1)
  uni.showToast({ title: '肩颈放松', icon: 'success' })
}
const syncStepCount = async () => {
  uni.showLoading({ title: '同步中' })
  setTimeout(async () => {
    const newSteps = Math.floor(Math.random() * 8000) + 2000
    await updateHealthMetric('stepCount', newSteps - stepCount.value)
    uni.hideLoading()
    uni.showToast({ title: `步数: ${stepCount.value}`, icon: 'none' })
  }, 1000)
}
const recordEnergySnack = async () => {
  await updateHealthMetric('energySnackCount', 1)
  uni.showToast({ title: '能量补充', icon: 'success' })
}
const recordStand = async () => {
  await updateHealthMetric('standCount', 1)
  uni.showToast({ title: '站起来啦', icon: 'success' })
}

// 本地推荐运动fallback
const getLocalRecommendedExercises = (occ) => {
  const map = {
    it: [{ id:1, name:'手腕屈伸', icon:'✋', shortDesc:'缓解鼠标手', detailUrl:'/pages/work/exercise-detail?id=1' },
         { id:2, name:'颈部侧屈', icon:'🦒', shortDesc:'放松颈椎', detailUrl:'/pages/work/exercise-detail?id=2' }],
    teacher: [{ id:4, name:'踮脚尖', icon:'🦶', shortDesc:'预防静脉曲张', detailUrl:'/pages/work/exercise-detail?id=4' }],
    driver: [{ id:6, name:'腰背拉伸', icon:'🧘', shortDesc:'缓解腰椎压力', detailUrl:'/pages/work/exercise-detail?id=6' }],
    student: [{ id:8, name:'眼保健操', icon:'👁️', shortDesc:'缓解视疲劳', detailUrl:'/pages/work/exercise-detail?id=8' }],
    medical: [{ id:10, name:'肩部绕环', icon:'🔄', shortDesc:'放松肩颈', detailUrl:'/pages/work/exercise-detail?id=10' }],
    admin: [{ id:12, name:'座椅拉伸', icon:'🪑', shortDesc:'背部放松', detailUrl:'/pages/work/exercise-detail?id=12' }],
    sales: [{ id:14, name:'靠墙静蹲', icon:'🧎', shortDesc:'强化腿部', detailUrl:'/pages/work/exercise-detail?id=14' }],
    general: [{ id:16, name:'颈部拉伸', icon:'🦒', shortDesc:'放松颈椎', detailUrl:'/pages/work/exercise-detail?id=16' }]
  }
  return map[occ] || map.general
}

const viewExerciseDetail = (ex) => {
  if (!ex.detailUrl) {
    uni.showToast({ title: '详情页路径不存在', icon: 'none' })
    return
  }
  uni.navigateTo({ url: ex.detailUrl })
}

// 番茄钟逻辑
const formattedTime = computed(() => {
  const mins = Math.floor(remainingSeconds.value / 60)
  const secs = remainingSeconds.value % 60
  return { minutes: String(mins).padStart(2, '0'), seconds: String(secs).padStart(2, '0') }
})

const tick = async () => {
  if (remainingSeconds.value <= 1) {
    if (isWorking.value) {
      // 专注完成，结束session
      if (currentSessionId) {
        await workApi.endSession(currentSessionId, new Date().toISOString(), WORK_DURATION)
        currentSessionId = null
      }
      // 刷新今日统计
      const todayStats = await workApi.getTodayStats()
      if (todayStats) {
        todayFocusMinutes.value = Number(todayStats.focusMinutes) || 0
        todaySessions.value = Number(todayStats.sessions) || 0
        todayPomodoros.value = Number(todayStats.sessions) || 0
      }
      isWorking.value = false
      remainingSeconds.value = BREAK_DURATION
      uni.showToast({ title: '专注结束，休息一下', icon: 'none' })
    } else {
      isWorking.value = true
      remainingSeconds.value = WORK_DURATION
      uni.showToast({ title: '休息结束，开始专注', icon: 'none' })
    }
  } else {
    remainingSeconds.value--
  }
}

const startTimer = async () => {
  if (isTimerRunning.value) return
  // 开始新的session
  if (!currentSessionId) {
    try {
      const session = await workApi.startSession(isWorking.value ? 'work' : 'break')
      currentSessionId = session.sessionId
    } catch (error) {
      console.error('开始session失败', error)
    }
  }
  isTimerRunning.value = true
  timerInterval = setInterval(tick, 1000)
}

const pauseTimer = () => {
  if (!isTimerRunning.value) return
  clearInterval(timerInterval)
  isTimerRunning.value = false
}

const resetTimer = async () => {
  pauseTimer()
  if (currentSessionId) {
    await workApi.endSession(currentSessionId, new Date().toISOString(), WORK_DURATION - remainingSeconds.value)
    currentSessionId = null
  }
  isWorking.value = true
  remainingSeconds.value = WORK_DURATION
  // 刷新今日统计
  const todayStats = await workApi.getTodayStats()
  if (todayStats) {
    todayFocusMinutes.value = Number(todayStats.focusMinutes) || 0
    todaySessions.value = Number(todayStats.sessions) || 0
    todayPomodoros.value = Number(todayStats.sessions) || 0
  }
}

// 久坐提醒
const startSedentaryReminder = () => {
  if (sedentaryTimer) clearInterval(sedentaryTimer)
  if (!sedentaryEnabled.value) return
  sedentaryTimer = setInterval(() => {
    uni.showModal({
      title: '久坐提醒',
      content: `您已连续工作 ${sedentaryInterval.value} 分钟，建议站起来活动一下。`,
      confirmText: '好的',
      success: async () => {
        // 记录响应
        try {
          await workApi.respondSedentary()
        } catch (error) {
          console.error('记录久坐响应失败', error)
        }
      }
    })
  }, sedentaryInterval.value * 60 * 1000)
}

const stopSedentaryReminder = () => {
  if (sedentaryTimer) clearInterval(sedentaryTimer)
  sedentaryTimer = null
}

const toggleSedentary = async (e) => {
  sedentaryEnabled.value = e.detail.value
  try {
    await workApi.updateSettings({
      sedentaryEnabled: sedentaryEnabled.value,
      sedentaryInterval: sedentaryInterval.value
    })
    if (sedentaryEnabled.value) startSedentaryReminder()
    else stopSedentaryReminder()
  } catch (error) {
    console.error('保存久坐设置失败', error)
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

const updateSedentaryInterval = async () => {
  let val = parseInt(sedentaryIntervalInput.value)
  if (isNaN(val) || val < 5) val = 5
  if (val > 180) val = 180
  sedentaryInterval.value = val
  sedentaryIntervalInput.value = String(val)
  try {
    await workApi.updateSettings({
      sedentaryEnabled: sedentaryEnabled.value,
      sedentaryInterval: sedentaryInterval.value
    })
    if (sedentaryEnabled.value) {
      stopSedentaryReminder()
      startSedentaryReminder()
    }
  } catch (error) {
    console.error('保存久坐间隔失败', error)
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

const goToPomodoro = () => {
  uni.navigateTo({ url: '/pages/work/pomodoro' })
}

// 职业切换
const goToOccupationSelect = () => {
  uni.navigateTo({
    url: '/pages/work/occupation-select'
  })
}

const applyOccupationChange = async (newOcc) => {
  if (currentOccupation.value === newOcc) return
  currentOccupation.value = newOcc
  try {
    // 保存职业设置到后端
    await workApi.updateSettings({ occupation: newOcc })
    // 重新加载职业健康数据
    await loadCareerHealthData()
    // 重新加载推荐运动
    const exercisesRes = await workApi.getRecommendedExercises(newOcc)
    const exercises = Array.isArray(exercisesRes) ? exercisesRes : (exercisesRes?.data || [])
    recommendedExercises.value = exercises.length
      ? exercises.map(ex => ({ ...ex, detailUrl: ex.detailUrl || `/pages/work/exercise-detail?id=${ex.id}` }))
      : getLocalRecommendedExercises(newOcc)
    // 更新久坐间隔（按职业调整）
    const intervalMap = { it:45, teacher:50, driver:60, student:40, medical:50, admin:55, sales:60, general:50 }
    const newInterval = intervalMap[newOcc] || 50
    sedentaryInterval.value = newInterval
    sedentaryIntervalInput.value = String(newInterval)
    await workApi.updateSettings({
      sedentaryEnabled: sedentaryEnabled.value,
      sedentaryInterval: sedentaryInterval.value
    })
    if (sedentaryEnabled.value) {
      stopSedentaryReminder()
      startSedentaryReminder()
    }
    uni.showToast({ title: `已切换到${currentOccupationLabel.value}模式`, icon: 'success' })
  } catch (error) {
    console.error('切换职业失败', error)
    uni.showToast({ title: '切换失败', icon: 'none' })
  }
}

// 生命周期
onMounted(async () => {
  uni.$on('occupationChanged', (data) => {
    applyOccupationChange(data.value)
  })

  if (!isLoggedIn) {
    uni.showModal({
      title: '提示',
      content: '请先登录使用工作模块',
      showCancel: false,
      success: () => uni.switchTab({ url: '/pages/index/index' })
    })
    return
  }
  
  await loadAllData()
})

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
  if (sedentaryTimer) clearInterval(sedentaryTimer)
  uni.$off('occupationChanged')
})
</script>

<style scoped>
.work-container {
  width: 100%;
  min-height: 100vh;
  background: linear-gradient(180deg, #f0f9f0 0%, #e8f5e9 100%);
  box-sizing: border-box;
}
.inner-wrapper {
  padding: 20rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
  width: 100%;
}
.greeting-card, .pomodoro-card, .reminder-card, .career-card, .stats-card, .exercises-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 48rpx;
  padding: 30rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 8rpx 20rpx rgba(0,0,0,0.05);
  border: 1px solid #d0e2d0;
}
.card-title {
  font-size: 36rpx;
  font-weight: 800;
  color: #2e7d32;
  margin-bottom: 8rpx;
}
.card-subtitle {
  font-size: 26rpx;
  color: #8d9e8d;
  margin-bottom: 20rpx;
}
.greeting-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.greeting-icon { font-size: 48rpx; }
.greeting-text { font-size: 30rpx; font-weight: 600; color: #2e7d32; flex:1; margin-left: 16rpx; }
.change-occupation { font-size: 26rpx; color: #558b2f; text-decoration: underline; }

.pomodoro-entry-card {
  background: rgba(255, 255, 255, 0.96);
  border-radius: 48rpx;
  padding: 28rpx;
  margin-bottom: 30rpx;
  border: 1rpx solid rgba(14, 165, 233, 0.16);
  box-shadow: 0 8rpx 18rpx rgba(14, 165, 233, 0.08);
}
.pomodoro-entry-desc {
  font-size: 28rpx;
  color: #2563eb;
  line-height: 1.8;
  margin: 20rpx 0;
}
.pomodoro-open-btn {
  width: 100%;
  height: 88rpx;
  border-radius: 48rpx;
  border: none;
  background: linear-gradient(135deg, #38bdf8, #0ea5e9);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 700;
}

.duration-card, .todo-card {
  background: rgba(255, 255, 255, 0.96);
  border-radius: 48rpx;
  padding: 28rpx;
  margin-bottom: 30rpx;
  border: 1rpx solid rgba(132, 204, 22, 0.18);
  box-shadow: 0 8rpx 18rpx rgba(34, 197, 94, 0.08);
}
.duration-value {
  display: block;
  margin-top: 18rpx;
  font-size: 40rpx;
  font-weight: 800;
  color: #15803d;
}
.duration-note {
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #4b5563;
}
.todo-input-row {
  display: flex;
  gap: 18rpx;
  margin-top: 24rpx;
  align-items: center;
}
.todo-input {
  flex: 1;
  height: 82rpx;
  border-radius: 42rpx;
  border: 1rpx solid #d1fae5;
  background: #f7fdf7;
  padding: 0 24rpx;
  font-size: 28rpx;
}
.add-todo-btn {
  min-width: 180rpx;
  height: 82rpx;
  border-radius: 42rpx;
  border: none;
  background: linear-gradient(135deg, #10b981, #059669);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 700;
}
.todo-list {
  margin-top: 24rpx;
}
.todo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  padding: 20rpx 0;
  border-bottom: 1rpx solid #ecfdf5;
}
.todo-text {
  font-size: 28rpx;
  color: #0f172a;
  flex: 1;
}
.todo-complete-btn {
  min-width: 170rpx;
  height: 70rpx;
  border-radius: 36rpx;
  border: none;
  background: #34d399;
  color: white;
  font-size: 26rpx;
}
.todo-empty {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  color: #6b7280;
}

/* ========== 番茄钟卡片美化（仅样式，不改结构） ========== */
.pomodoro-card {
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(20px);
  border-radius: 72rpx;
  padding: 40rpx 30rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 20rpx 40rpx rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.6);
  transition: all 0.3s ease;
}
.timer-display {
  text-align: center;
  background: linear-gradient(145deg, #fff8f0, #fff3e0);
  width: 80%;
  margin: 0 auto;
  border-radius: 120rpx;
  padding: 30rpx 20rpx;
  box-shadow: inset 0 2rpx 4rpx rgba(0,0,0,0.02), 0 8rpx 20rpx rgba(0,0,0,0.05);
}
.timer-minutes, .timer-seconds {
  font-size: 96rpx;
  font-weight: 800;
  background: linear-gradient(135deg, #ef6c00, #d98c2b);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: 0 2rpx 4rpx rgba(0,0,0,0.05);
}
.timer-colon {
  font-size: 88rpx;
  font-weight: 700;
  color: #ef6c00;
  margin: 0 8rpx;
}
.timer-status {
  margin-top: 20rpx;
  text-align: center;
}
.status-text {
  font-size: 30rpx;
  font-weight: 600;
  color: #ef6c00;
  background: rgba(255,245,220,0.9);
  padding: 8rpx 32rpx;
  border-radius: 60rpx;
  display: inline-block;
  backdrop-filter: blur(4px);
}
.timer-controls {
  display: flex;
  justify-content: center;
  gap: 30rpx;
  margin-top: 30rpx;
  margin-bottom: 20rpx;
}
.timer-btn {
  border-radius: 60rpx;
  padding: 15rpx 80rpx;   
  font-size: 34rpx;
  font-weight: 700;
  border: none;
  transition: all 0.2s ease;
  box-shadow: 0 6rpx 14rpx rgba(0,0,0,0.1);
  min-width: 180rpx;
}
.timer-btn.start {
  background: linear-gradient(135deg, #43a047, #2e7d32);
  color: white;
}
.timer-btn.pause {
  background: linear-gradient(135deg, #ffb74d, #ef6c00);
  color: white;
}
.timer-btn.reset {
  background: linear-gradient(135deg, #ef9a9a, #e53935);
  color: white;
}
.timer-btn:active {
  transform: scale(0.96);
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.1);
}
.pomodoro-stats {
  text-align: center;
  font-size: 28rpx;
  color: #5c7a5c;
  padding-top: 20rpx;
  border-top: 1px solid #e8f5e9;
  margin-top: 10rpx;
}

/* 其余原有样式（久坐提醒、职业卡片、统计、微运动等）保持不变 */
.reminder-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.reminder-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0;
  border-top: 1px solid #e8f5e9;
}
.interval-input {
  width: 120rpx;
  background: #f5f9f5;
  border-radius: 32rpx;
  padding: 12rpx 20rpx;
  text-align: center;
  font-size: 28rpx;
  border: 1px solid #d0e2d0;
}
.unit {
  margin-left: 12rpx;
  font-size: 26rpx;
  color: #8d9e8d;
}
.career-content {
  margin-top: 20rpx;
}
.health-metric {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 0;
  border-bottom: 1px solid #e8f5e9;
}
.metric-label {
  font-size: 28rpx;
  color: #2c3e2f;
}
.metric-value {
  font-size: 32rpx;
  font-weight: 700;
  color: #c27e2a;
}
.action-btn {
  background: #e8f5e9;
  border: none;
  border-radius: 60rpx;
  padding: 8rpx 24rpx;
  font-size: 24rpx;
  color: #2e7d32;
}
.stats-grid {
  display: flex;
  justify-content: space-around;
  margin-bottom: 30rpx;
}
.stat-item {
  text-align: center;
}
.stat-value {
  font-size: 48rpx;
  font-weight: 800;
  color: #c27e2a;
  display: block;
}
.stat-label {
  font-size: 26rpx;
  color: #5a7a4a;
}
.weekly-trend {
  border-top: 1px solid #e8f5e9;
  padding-top: 20rpx;
}
.trend-bars {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  height: 200rpx;
}
.bar {
  background: #66bb6a;
  width: 40rpx;
  margin: 0 auto;
  border-radius: 20rpx 20rpx 0 0;
  min-height: 20rpx;
}
.bar-label {
  font-size: 22rpx;
  color: #8d9e8d;
  margin-top: 8rpx;
  text-align: center;
}
.exercise-item {
  display: flex;
  align-items: center;
  padding: 20rpx 0;
  border-bottom: 1px solid #e8f5e9;
}
.exercise-icon {
  font-size: 48rpx;
  margin-right: 20rpx;
}
.exercise-info {
  flex: 1;
}
.exercise-name {
  font-size: 30rpx;
  font-weight: 600;
  color: #2c3e2f;
}
.exercise-desc {
  font-size: 26rpx;
  color: #8d9e8d;
}
.exercise-arrow {
  font-size: 40rpx;
  color: #b0bec5;
}
</style>