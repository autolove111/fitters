import { reactive, computed } from 'vue'
import { request } from '../utils/api'
import { getDevAuthUser, isDevAuthBypass } from '../utils/auth'

const state = reactive({
  token: '',
  username: '',
  userId: '',
  role: '',
  isAdmin: false,
  authEnabled: false,
  authenticated: false,
})

const init = () => {
  state.token = uni.getStorageSync('dt_token') || ''
  state.username = uni.getStorageSync('dt_username') || ''
  state.userId = uni.getStorageSync('dt_user_id') || ''
  state.role = uni.getStorageSync('dt_role') || ''
  state.isAdmin = uni.getStorageSync('dt_is_admin') === true
  state.authenticated = uni.getStorageSync('dt_authenticated') === true
}

const isLoggedIn = computed(() => !state.authEnabled || state.authenticated || !!state.token)

const setUser = ({ token, username, user_id, role, is_admin, authenticated = true }) => {
  state.token = token || ''
  state.username = username || ''
  state.userId = user_id || ''
  state.role = role || ''
  state.isAdmin = !!is_admin
  state.authenticated = !!authenticated
  if (token) uni.setStorageSync('dt_token', token)
  else uni.removeStorageSync('dt_token')
  uni.setStorageSync('dt_username', state.username)
  uni.setStorageSync('dt_user_id', state.userId)
  uni.setStorageSync('dt_role', state.role)
  uni.setStorageSync('dt_is_admin', state.isAdmin)
  uni.setStorageSync('dt_authenticated', state.authenticated)
}

const clearUser = () => {
  state.token = ''
  state.username = ''
  state.userId = ''
  state.role = ''
  state.isAdmin = false
  state.authenticated = false
  uni.removeStorageSync('dt_token')
  uni.removeStorageSync('dt_username')
  uni.removeStorageSync('dt_user_id')
  uni.removeStorageSync('dt_role')
  uni.removeStorageSync('dt_is_admin')
  uni.removeStorageSync('dt_authenticated')
}

const login = async (username, password) => {
  if (isDevAuthBypass()) {
    const devUser = getDevAuthUser()
    setUser({
      username: username || devUser.username,
      user_id: devUser.user_id,
      role: devUser.role,
      is_admin: devUser.is_admin,
      authenticated: true,
    })
    state.authEnabled = false
    return { ...devUser, username: username || devUser.username }
  }
  await request('/api/v1/auth/login', {
    method: 'POST',
    data: { username, password },
  })
  const status = await fetchStatus()
  if (!status.authenticated) {
    throw new Error('登录成功，但未建立会话')
  }
  return status
}

const register = async (username, password) => {
  if (isDevAuthBypass()) {
    return login(username, password)
  }
  await request('/api/v1/auth/register', {
    method: 'POST',
    data: { username, password },
  })
  return login(username, password)
}

const logout = async () => {
  if (isDevAuthBypass()) {
    clearUser()
    uni.reLaunch({ url: '/pages/study/aidlearning/index/index' })
    return
  }
  try {
    await request('/api/v1/auth/logout', { method: 'POST' })
  } catch (e) {}
  clearUser()
  uni.reLaunch({ url: '/pages/study/aidlearning/login/login' })
}

const fetchStatus = async () => {
  if (isDevAuthBypass()) {
    const devUser = getDevAuthUser()
    state.authEnabled = false
    setUser({
      username: state.username || devUser.username,
      user_id: state.userId || devUser.user_id,
      role: state.role || devUser.role,
      is_admin: state.isAdmin || devUser.is_admin,
      authenticated: true,
    })
    return {
      ...devUser,
      username: state.username || devUser.username,
      user_id: state.userId || devUser.user_id,
      role: state.role || devUser.role,
      is_admin: state.isAdmin || devUser.is_admin,
    }
  }
  const res = await request('/api/v1/auth/status')
  state.authEnabled = !!res.enabled
  if (!res.enabled) {
    setUser({
      username: res.username,
      user_id: res.user_id,
      role: res.role,
      is_admin: res.is_admin,
      authenticated: true,
    })
  } else if (res.authenticated) {
    setUser({
      token: state.token,
      username: res.username,
      user_id: res.user_id,
      role: res.role,
      is_admin: res.is_admin,
      authenticated: true,
    })
  } else {
    clearUser()
  }
  return res
}

export const useUserStore = () => {
  init()
  return { state, isLoggedIn, setUser, clearUser, login, register, logout, fetchStatus }
}
