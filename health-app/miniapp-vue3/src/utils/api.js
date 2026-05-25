const BASE_URL = 'http://localhost:18080/api'  // 开发环境后端地址

// 获取存储的 token
const getToken = () => uni.getStorageSync('auth_token') || ''

// 统一请求函数
export const request = (url, options = {}) => {
  return new Promise((resolve, reject) => {
    const token = getToken()
    const header = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.header
    }
    uni.request({
      url: `${BASE_URL}${url}`,
      method: options.method || 'GET',
      data: options.data,
      header,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          // 处理后端 {code, data, message} 格式
          const payload = res.data
          if (payload && typeof payload === 'object' && 'code' in payload && 'data' in payload) {
            resolve(payload.data)
          } else {
            resolve(payload)
          }
        } else {
          reject(new Error(res.data?.message || '请求失败'))
        }
      },
      fail: reject
    })
  })
}

// 封装具体 API
export const auth = {
  login: (account, password) => request('/auth/login', { method: 'POST', data: { account, password } }),
  register: (account, password) => request('/auth/register', { method: 'POST', data: { account, password } })
}

export const workoutApi = {
  add: (data) => request('/workouts', { method: 'POST', data }),
  list: () => request('/workouts'),
  delete: (id) => request(`/workouts/${id}`, { method: 'DELETE' })
}

export const sleepApi = {
  add: (data) => request('/sleeps', { method: 'POST', data }),
  list: () => request('/sleeps')
}

export const dietApi = {
  add: (data) => request('/diets', { method: 'POST', data }),
  list: () => request('/diets')
}

export const statsApi = {
  today: () => request('/stats/today'),
  weekly: () => request('/stats/weekly'),
  summary: () => request('/stats/summary'),
  sleepToday: () => request('/stats/sleep/today'), 
  dietToday: () => request('/stats/diet/today'),  
  getHistory: (params = { days: 30 }) => request('/stats/history', { data: params }),
  generatePlan: (userData) => request('/plans/today-workout', { method: 'POST', data: userData })
}

export const goalApi = {
  set: (targetValue) => request('/goals', { method: 'POST', data: { targetValue } })
}

export const wellnessApi = {
  getAdvice: (data) => request('/wellness/advice', { method: 'POST', data }),
  getTodayCheckin: () => request('/checkin/today', { method: 'GET' }),
  // 保存今日打卡数据（提交任务完成状态）
  saveTodayCheckin: (tasks) => request('/checkin/today', { method: 'POST', data: { tasks } }),
  // 获取指定月份的打卡记录列表（用于月度报告）
  getMonthlyCheckin: (yearMonth) => request(`/checkin/monthly/${yearMonth}`, { method: 'GET' }),
  // 获取所有打卡历史（用于徽章计算，可选）
  getAllCheckinHistory: () => request('/checkin/history', { method: 'GET' })
}

// ========== 工作模块 API ==========
export const workApi = {
  // 获取用户工作设置（包含职业、番茄钟时长、久坐提醒开关等）
  getSettings: () => request('/work/settings', { method: 'GET' }),
  // 更新用户工作设置
  updateSettings: (data) => request('/work/settings', { method: 'PUT', data }),
  // 开始一个工作会话（番茄钟）
  startSession: (type) => request('/work/session/start', { method: 'POST', data: { type, startTime: new Date().toISOString() } }),
  // 结束工作会话
  endSession: (sessionId, endTime, duration) => request('/work/session/end', { method: 'PUT', data: { sessionId, endTime, duration } }),
  // 获取今日统计数据
  getTodayStats: () => request('/work/stats/daily', { method: 'GET' }),
  // 获取本周趋势数据
  getWeeklyStats: () => request('/work/stats/weekly', { method: 'GET' }),
  // 记录用户响应久坐提醒
  respondSedentary: () => request('/work/sedentary/respond', { method: 'POST', data: { timestamp: new Date().toISOString() } }),
  // 获取职业推荐微运动列表
  getRecommendedExercises: (occupation) => request(`/work/exercises/recommended?occupation=${occupation}`, { method: 'GET' }),
  // 获取所有微运动列表（用于详情页）
  getAllExercises: () => request('/work/exercises', { method: 'GET' }),
    // 获取用户健康数据（职业专属指标）
  getHealthData: (occupation) => request(`/work/health-data?occupation=${occupation}`, { method: 'GET' }),
  // 更新单个健康指标
  updateHealthMetric: (data) => request('/work/health-data/metric', { method: 'POST', data }),
}

// ========== 个人知识助手（学习页使用） ==========
export const studyApi = {
  list: () => request('/study/plans'),
  add: (data) => request('/study/plans', { method: 'POST', data })
}

export const assistantApi = {
  // 将用户输入发送到后端知识助手接口，后端负责返回 AI 回复
  chat: (payload) => request('/assistant/chat', { method: 'POST', data: payload })
}