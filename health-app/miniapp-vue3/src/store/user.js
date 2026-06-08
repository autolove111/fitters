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
  state.avatar = toFullUrl(uni.getStorageSync('auth_avatar') || '')
}

const setUser = (token, username, nickname = '', avatar = '') => {
  if (token && username) {
    state.token = token
    state.username = username
    state.nickname = nickname
    state.avatar = toFullUrl(avatar)
    uni.setStorageSync('auth_token', token)
    uni.setStorageSync('auth_username', username)
    if (nickname) uni.setStorageSync('auth_nickname', nickname)
    if (avatar) uni.setStorageSync('auth_avatar', toFullUrl(avatar))
  } else {
    uni.removeStorageSync('auth_token')
    uni.removeStorageSync('auth_username')
  }
}

// 显示名称：优先昵称，其次用户名
const displayName = computed(() => state.nickname || state.username || '')

// 后端静态资源基地址（去掉 /api 后缀）
const STATIC_BASE = 'http://localhost:18080'

// 将相对路径补全为完整 URL
function toFullUrl(url) {
  if (!url) return url
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) return url
  if (url.startsWith('/')) return STATIC_BASE + url
  return url
}

// 从后端返回数据中提取头像 URL
const extractAvatarUrl = (data) => {
  if (typeof data === 'string') return toFullUrl(data)
  if (data && typeof data === 'object') {
    const keys = ['url', 'avatar', 'avatarUrl', 'avatar_url', 'imageUrl', 'image_url', 'path', 'href', 'src']
    for (const k of keys) {
      if (typeof data[k] === 'string' && data[k]) return toFullUrl(data[k])
    }
  }
  return null
}

// 从后端加载头像
const loadAvatar = async () => {
  try {
    const data = await userApi.getAvatar()
    const url = extractAvatarUrl(data)
    if (url) {
      state.avatar = url
      uni.setStorageSync('auth_avatar', url)
      return
    }
  } catch (e) {
    console.warn('从后端获取头像失败，使用本地缓存', e)
  }
  state.avatar = toFullUrl(uni.getStorageSync('auth_avatar') || '')
}

// 保存头像：上传后端获取远程 URL
const saveAvatar = async (filePath) => {
  const data = await userApi.uploadAvatar(filePath)
  const url = extractAvatarUrl(data)
  if (url) {
    state.avatar = url
    uni.setStorageSync('auth_avatar', url)
    return
  }
  throw new Error('头像上传失败，请重试')
}

// 从后端加载用户资料（昵称等）
const loadProfile = async () => {
  try {
    const data = await userApi.getProfile()
    if (data) {
      if (data.nickname !== undefined && data.nickname !== null) {
        state.nickname = data.nickname
        uni.setStorageSync('auth_nickname', data.nickname)
      }
      if (data.username) {
        state.username = data.username
        uni.setStorageSync('auth_username', data.username)
      }
      if (data.avatar !== undefined && data.avatar !== null) {
        const avatarUrl = toFullUrl(data.avatar)
        state.avatar = avatarUrl
        uni.setStorageSync('auth_avatar', avatarUrl)
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
