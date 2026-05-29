import { reactive, computed } from 'vue'
import { userApi } from '@/utils/api'

const state = reactive({
  token: '',
  username: '',
  nickname: '',
  avatar: ''
})

const init = () => {
  state.token = uni.getStorageSync('auth_token') || ''
  state.username = uni.getStorageSync('auth_username') || ''
  state.nickname = uni.getStorageSync('auth_nickname') || ''
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

// 显示名称：优先昵称，其次用户名
const displayName = computed(() => state.nickname || state.username || '')

// 从后端加载头像
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
  state.avatar = uni.getStorageSync('auth_avatar') || ''
}

// 保存头像：先本地再上传后端
const saveAvatar = async (filePath) => {
  state.avatar = filePath
  uni.setStorageSync('auth_avatar', filePath)
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

// 从后端加载用户资料（昵称等）
const loadProfile = async () => {
  try {
    const data = await userApi.getProfile()
    if (data) {
      if (data.nickname) {
        state.nickname = data.nickname
        uni.setStorageSync('auth_nickname', data.nickname)
      }
      if (data.username && !state.username) {
        state.username = data.username
        uni.setStorageSync('auth_username', data.username)
      }
    }
  } catch (e) {
    console.warn('获取用户资料失败', e)
  }
}

// 更新昵称
const saveNickname = async (nickname) => {
  state.nickname = nickname
  uni.setStorageSync('auth_nickname', nickname)
  try {
    await userApi.updateProfile({ nickname })
  } catch (e) {
    console.warn('同步昵称到后端失败', e)
  }
}

const clearUser = () => {
  state.token = ''
  state.username = ''
  state.nickname = ''
  state.avatar = ''
  uni.removeStorageSync('auth_token')
  uni.removeStorageSync('auth_username')
  uni.removeStorageSync('auth_nickname')
  uni.removeStorageSync('auth_avatar')
}

const isLoggedIn = computed(() => !!state.token)

export const useUserStore = () => {
  init()
  return {
    state,
    displayName,
    setUser,
    loadAvatar,
    saveAvatar,
    loadProfile,
    saveNickname,
    clearUser,
    isLoggedIn
  }
}
