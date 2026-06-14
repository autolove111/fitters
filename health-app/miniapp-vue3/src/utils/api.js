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

// 统一文件上传函数
export const uploadFile = (url, filePath, name = 'avatar') => {
  return new Promise((resolve, reject) => {
    const token = getToken()
    uni.uploadFile({
      url: `${BASE_URL}${url}`,
      filePath,
      name,
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            const payload = JSON.parse(res.data)
            resolve(payload?.data ?? payload)
          } catch {
            resolve(res.data)
          }
        } else {
          reject(new Error('上传失败'))
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
  generatePlan: (userData) => request('/plans/today-workout', { method: 'POST', data: userData }),
  generatePersonalizedPlan: (userData) => request('/plans/personalized-workout', { method: 'POST', data: userData })
}

export const fitnessProfileApi = {
  get: () => request('/users/fitness-profile'),
  save: (data) => request('/users/fitness-profile', { method: 'PUT', data })
}

export const membershipApi = {
  get: () => request('/membership'),
  setMockTier: (tier) => request('/membership/mock-tier', { method: 'PUT', data: { tier } })
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
  // 获取今日工作时长
  getTodayWorkDuration: () => request('/work/today-duration', { method: 'GET' }),
  // TODO
  getTodayTodos: () => request('/work/todos/today', { method: 'GET' }),
  addTodayTodo: (content, deadline) => request('/work/todos', { method: 'POST', data: { content, deadline } }),
  completeTodo: (todoId) => request(`/work/todos/${todoId}`, { method: 'DELETE' }),
  // 获取用户健康数据（职业专属指标）
  getHealthData: (occupation) => request(`/work/health-data?occupation=${occupation}`, { method: 'GET' }),
  // 更新单个健康指标
  updateHealthMetric: (data) => request('/work/health-data/metric', { method: 'POST', data }),
}

// ========== 学习模块API ==========
export const studyApi = {
  list: () => request('/study/plans'),
  add: (data) => request('/study/plans', { method: 'POST', data }),
  delete: (id) => request(`/study/plans/${id}`, { method: 'DELETE' }),
}

// ========== 知识库API（走 deeptutor 后端）==========
const DT_BASE = uni.getStorageSync('api_base') || 'http://localhost:8001'
const getDtToken = () => uni.getStorageSync('dt_token') || ''

export const knowledgeApi = {
  list: () => {
    return new Promise((resolve, reject) => {
      uni.request({
        url: `${DT_BASE}/api/v1/knowledge/list`,
        method: 'GET',
        header: { Authorization: `Bearer ${getDtToken()}` },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data)
          else reject(new Error(res.data?.detail || '请求失败'))
        },
        fail: reject
      })
    })
  },
  detail: (name) => {
    return new Promise((resolve, reject) => {
      uni.request({
        url: `${DT_BASE}/api/v1/knowledge/${name}`,
        method: 'GET',
        header: { Authorization: `Bearer ${getDtToken()}` },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data)
          else reject(new Error(res.data?.detail || '请求失败'))
        },
        fail: reject
      })
    })
  },
  upload: (name, filePath) => {
    return new Promise((resolve, reject) => {
      uni.uploadFile({
        url: `${DT_BASE}/api/v1/knowledge/${name}/upload`,
        filePath,
        name: 'files',
        header: { Authorization: `Bearer ${getDtToken()}` },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(typeof res.data === 'string' ? JSON.parse(res.data) : res.data)
          } else {
            let msg = '上传失败'
            try { msg = JSON.parse(res.data)?.detail || msg } catch {}
            reject(new Error(msg))
          }
        },
        fail: (err) => reject(new Error(err.errMsg || '上传失败'))
      })
    })
  },
  create: (name, filePath) => {
    return new Promise((resolve, reject) => {
      uni.uploadFile({
        url: `${DT_BASE}/api/v1/knowledge/create`,
        filePath,
        name: 'files',
        formData: { name },
        header: { Authorization: `Bearer ${getDtToken()}` },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(typeof res.data === 'string' ? JSON.parse(res.data) : res.data)
          } else {
            let msg = '创建失败'
            try { msg = JSON.parse(res.data)?.detail || msg } catch {}
            reject(new Error(msg))
          }
        },
        fail: (err) => reject(new Error(err.errMsg || '创建失败'))
      })
    })
  },
}

export const assistantApi = {
  // 将用户输入发送到后端知识助手接口，后端负责返回 AI 回复
  chat: (payload) => request('/assistant/chat', { method: 'POST', data: payload })
}

// ========== 用户模块 API ==========
export const userApi = {
  getAvatar: () => request('/users/avatar', { method: 'GET' }),
  uploadAvatar: (filePath) => uploadFile('/users/avatar', filePath),
  getProfile: () => request('/users/profile', { method: 'GET' }),
  updateProfile: (data) => request('/users/profile', { method: 'PUT', data }),
  changePassword: (data) => request('/users/password', { method: 'PUT', data }),
  deleteAccount: () => request('/users/account', { method: 'DELETE' }),
}

// ========== 主题模块 API ==========
export const themeApi = {
  getTheme: () => request('/users/theme', { method: 'GET' }),
  updateTheme: (mode) => request('/users/theme', { method: 'PUT', data: { mode } }),
}

// ========== 饮水模块 API ==========
export const waterApi = {
  add: (data) => request('/waters', { method: 'POST', data }),
  list: () => request('/waters'),
  today: () => request('/waters/today', { method: 'GET' }),
}

// ========== 体重模块 API ==========
export const weightApi = {
  add: (data) => request('/weights', { method: 'POST', data }),
  today: () => request('/weights/today', { method: 'GET' }),
}
