import { isDevAuthBypass } from './auth'

const getBaseUrl = () => uni.getStorageSync('api_base') || 'http://localhost:8001'

const getToken = () => uni.getStorageSync('dt_token') || ''
const clearAuthStorage = () => {
  uni.removeStorageSync('dt_token')
  uni.removeStorageSync('dt_username')
  uni.removeStorageSync('dt_user_id')
  uni.removeStorageSync('dt_role')
  uni.removeStorageSync('dt_is_admin')
  uni.removeStorageSync('dt_authenticated')
}

export const setApiBase = (url) => uni.setStorageSync('api_base', url)
export const getApiBase = getBaseUrl

export const request = (url, options = {}) => {
  return new Promise((resolve, reject) => {
    const token = getToken()
    const header = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.header,
    }
    uni.request({
      url: `${getBaseUrl()}${url}`,
      method: options.method || 'GET',
      data: options.data,
      header,
      withCredentials: true,
      enableCookie: true,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else if (res.statusCode === 401) {
          clearAuthStorage()
          if (!isDevAuthBypass()) {
            uni.reLaunch({ url: '/pages/study/deeptutor/login/login' })
          }
          reject(new Error(isDevAuthBypass() ? '开发模式下已跳过登录跳转，但接口仍返回未授权' : '未授权，请重新登录'))
        } else {
          reject(new Error(res.data?.detail || res.data?.message || `请求失败 (${res.statusCode})`))
        }
      },
      fail: (err) => reject(new Error(err.errMsg || '网络错误')),
    })
  })
}

export const upload = (url, filePath, formData = {}, name = 'file') => {
  return new Promise((resolve, reject) => {
    const token = getToken()
    uni.uploadFile({
      url: `${getBaseUrl()}${url}`,
      filePath,
      name,
      formData,
      header: token ? { Authorization: `Bearer ${token}` } : {},
      withCredentials: true,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(typeof res.data === 'string' ? JSON.parse(res.data) : res.data)
        } else {
          reject(new Error('上传失败'))
        }
      },
      fail: (err) => reject(new Error(err.errMsg || '上传失败')),
    })
  })
}
