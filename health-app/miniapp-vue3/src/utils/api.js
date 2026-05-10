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
  getHistory: (params = { days: 30 }) => request('/stats/history', { data: params }),
  generatePlan: (userData) => request('/ai/generate-plan', { method: 'POST', data: userData })
}

export const goalApi = {
  set: (targetValue) => request('/goals', { method: 'POST', data: { targetValue } })
}