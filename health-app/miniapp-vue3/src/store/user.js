import { reactive, computed } from 'vue'
import { userApi } from '@/utils/api'

const state = reactive({
  token: '',
  username: '',
  avatar: ''
})

// 初始化从本地读取
const init = () => {
  state.token = uni.getStorageSync('auth_token') || ''
  state.username = uni.getStorageSync('auth_username') || ''
  state.avatar = uni.getStorageSync('auth_avatar') || ''
}

const setUser = (token, username) => {
  if (token && username) {
    state.token = token
    state.username = username
    uni.setStorageSync('auth_token', token)
    uni.setStorageSync('auth_username', username)
  } else {
    uni.removeStorageSync('auth_token')
    uni.removeStorageSync('auth_username')
  }
}

// 从后端加载头像，失败则用本地缓存
const loadAvatar = async () => {
  try {
    const data = await userApi.getAvatar()
    const url = data?.url || data?.avatar || data
    if (url && typeof url === 'string') {
      state.avatar = url
      uni.setStorageSync('auth_avatar', url)
      return
    }
  } catch (e) {
    console.warn('从后端获取头像失败，使用本地缓存', e)
  }
  // fallback: 本地缓存
  state.avatar = uni.getStorageSync('auth_avatar') || ''
}

// 保存头像：先上传后端，失败则存本地
const saveAvatar = async (filePath) => {
  // 先存本地，保证即时生效
  state.avatar = filePath
  uni.setStorageSync('auth_avatar', filePath)
  // 尝试上传后端
  try {
    const data = await userApi.uploadAvatar(filePath)
    const url = data?.url || data?.avatar || data
    if (url && typeof url === 'string') {
      state.avatar = url
      uni.setStorageSync('auth_avatar', url)
    }
  } catch (e) {
    console.warn('上传头像到后端失败，已保留本地缓存', e)
  }
}

const clearUser = () => {
  state.token = ''
  state.username = ''
  state.avatar = ''
  uni.removeStorageSync('auth_token')
  uni.removeStorageSync('auth_username')
  uni.removeStorageSync('auth_avatar')
}

const isLoggedIn = computed(() => !!state.token)

export const useUserStore = () => {
  init()
  return {
    state,
    setUser,
    loadAvatar,
    saveAvatar,
    clearUser,
    isLoggedIn
  }
}
