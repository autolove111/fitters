import { reactive, computed } from 'vue'

const state = reactive({
  token: '',
  username: ''
})

// 初始化从本地读取
const init = () => {
  state.token = uni.getStorageSync('auth_token') || ''
  state.username = uni.getStorageSync('auth_username') || ''
}

const setUser = (token, username) => {
  if (token && username) {
    state.token = token
    state.username = username
    uni.setStorageSync('auth_token', token)
    uni.setStorageSync('auth_username', username)
  } else {
    // 否则清除不完整的数据
    uni.removeStorageSync('auth_token')
    uni.removeStorageSync('auth_username')
  }
}

const clearUser = () => {
  state.token = ''
  state.username = ''
  uni.removeStorageSync('auth_token')
  uni.removeStorageSync('auth_username')
}

const isLoggedIn = computed(() => !!state.token)
//const isLoggedIn = true

export const useUserStore = () => {
  init()
  return {
    state,
    setUser,
    clearUser,
    isLoggedIn
  }
}