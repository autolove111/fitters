import { reactive } from 'vue'
import { request } from '../utils/api'

const state = reactive({
  theme: 'light',
  language: 'zh',
  catalog: null,
  providers: null,
  systemStatus: null,
  uiSettings: null,
  llmOptions: [],
  themes: [],
})

const loadSettings = async () => {
  const res = await request('/api/v1/settings')
  state.uiSettings = res.ui || {}
  state.catalog = res.catalog || null
  state.providers = res.providers || null
  if (res.ui?.theme) state.theme = res.ui.theme
  if (res.ui?.language) state.language = res.ui.language
  return res
}

const loadSystemStatus = async () => {
  const res = await request('/api/v1/system/status')
  state.systemStatus = res
  return res
}

const loadLLMOptions = async () => {
  const res = await request('/api/v1/settings/llm-options')
  state.llmOptions = res.options || res || []
  return state.llmOptions
}

const loadThemes = async () => {
  const res = await request('/api/v1/settings/themes')
  state.themes = res.themes || res || []
  return state.themes
}

const updateTheme = async (theme) => {
  await request('/api/v1/settings/theme', { method: 'PUT', data: { theme } })
  state.theme = theme
}

const updateLanguage = async (language) => {
  await request('/api/v1/settings/language', { method: 'PUT', data: { language } })
  state.language = language
}

const loadCatalog = async () => {
  const res = await request('/api/v1/settings/catalog')
  state.catalog = res.catalog || null
  return state.catalog
}

const updateCatalog = async (catalog) => {
  const res = await request('/api/v1/settings/catalog', {
    method: 'PUT',
    data: { catalog },
  })
  state.catalog = res.catalog || catalog
  return state.catalog
}

const applyCatalog = async (catalog = null) => {
  const res = await request('/api/v1/settings/apply', {
    method: 'POST',
    data: catalog ? { catalog } : undefined,
  })
  state.catalog = res.catalog || state.catalog
  return res
}

const loadTools = async () => {
  return await request('/api/v1/tools')
}

const updateEnabledTools = async (enabledTools) => {
  await request('/api/v1/settings/enabled-tools', {
    method: 'PUT',
    data: { enabled_optional_tools: enabledTools },
  })
}

const testService = async (service) => {
  return await request(`/api/v1/settings/tests/${service}/start`, { method: 'POST' })
}

const testLLMConnection = async () => {
  return await request('/api/v1/system/test/llm', { method: 'POST' })
}

export const useSettingsStore = () => {
  return {
    state,
    loadSettings,
    loadSystemStatus,
    loadLLMOptions,
    loadThemes,
    updateTheme,
    updateLanguage,
    loadCatalog,
    updateCatalog,
    applyCatalog,
    loadTools,
    updateEnabledTools,
    testService,
    testLLMConnection,
  }
}
