import { reactive, computed } from 'vue'
import { themeApi } from '@/utils/api'

const state = reactive({
  mode: 'light'
})

const init = async () => {
  // 优先从本地缓存读取，保证快速渲染
  state.mode = uni.getStorageSync('theme_mode') || 'light'
  applyNavBarStyle()
  // 尝试从后端获取最新设置
  try {
    const data = await themeApi.getTheme()
    if (data && data.mode) {
      state.mode = data.mode
      uni.setStorageSync('theme_mode', data.mode)
      applyNavBarStyle()
    }
  } catch (e) {
    console.warn('获取主题设置失败，使用本地缓存', e)
  }
}

const isDark = computed(() => state.mode === 'dark')

const setTheme = async (mode) => {
  state.mode = mode
  uni.setStorageSync('theme_mode', mode)
  applyNavBarStyle()
  try {
    await themeApi.updateTheme(mode)
  } catch (e) {
    console.warn('同步主题到后端失败', e)
    uni.showToast({ title: '主题设置同步失败', icon: 'none' })
  }
}

const toggleTheme = () => {
  setTheme(state.mode === 'dark' ? 'light' : 'dark')
}

const applyNavBarStyle = () => {
  const dark = state.mode === 'dark'
  uni.setNavigationBarColor({
    frontColor: dark ? '#ffffff' : '#000000',
    backgroundColor: dark ? '#1a1a2e' : '#F8F8F8'
  })
}

export const useThemeStore = () => {
  init()
  return {
    state,
    isDark,
    setTheme,
    toggleTheme,
    applyNavBarStyle
  }
}
