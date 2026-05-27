import { request } from '../utils/api'

export const capabilitiesApi = {
  getSettings: () => request('/api/v1/capabilities/settings'),
  putSettings: (data) => request('/api/v1/capabilities/settings', { method: 'PUT', data }),
}
