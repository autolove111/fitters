import { request } from '../utils/api'

export const settingsApi = {
  get: () => request('/api/v1/settings'),
  getCatalog: () => request('/api/v1/settings/catalog'),
  putCatalog: (data) => request('/api/v1/settings/catalog', { method: 'PUT', data }),
  apply: () => request('/api/v1/settings/apply', { method: 'POST' }),
  getLLMOptions: () => request('/api/v1/settings/llm-options'),
  putTheme: (theme) => request('/api/v1/settings/theme', { method: 'PUT', data: { theme } }),
  putLanguage: (language) => request('/api/v1/settings/language', { method: 'PUT', data: { language } }),
  putUI: (data) => request('/api/v1/settings/ui', { method: 'PUT', data }),
  reset: () => request('/api/v1/settings/reset', { method: 'POST' }),
  getThemes: () => request('/api/v1/settings/themes'),
  getSidebar: () => request('/api/v1/settings/sidebar'),
  putSidebarDescription: (description) => request('/api/v1/settings/sidebar/description', { method: 'PUT', data: { description } }),
  putSidebarNavOrder: (nav_order) => request('/api/v1/settings/sidebar/nav-order', { method: 'PUT', data: { nav_order } }),
  putEnabledTools: (enabled_optional_tools) => request('/api/v1/settings/enabled-tools', { method: 'PUT', data: { enabled_optional_tools } }),
  testService: (service) => request(`/api/v1/settings/tests/${service}/start`, { method: 'POST' }),
  tourStatus: () => request('/api/v1/settings/tour/status'),
  tourComplete: () => request('/api/v1/settings/tour/complete', { method: 'POST' }),
  tourReopen: () => request('/api/v1/settings/tour/reopen', { method: 'POST' }),
}
