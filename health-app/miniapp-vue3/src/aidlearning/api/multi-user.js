import { request } from '../utils/api'

export const multiUserApi = {
  meAccess: () => request('/api/v1/multi-user/me/access'),
  adminResources: () => request('/api/v1/multi-user/admin/resources'),
  getGrants: (userId) => request(`/api/v1/multi-user/users/${userId}/grants`),
  updateGrants: (userId, data) => request(`/api/v1/multi-user/users/${userId}/grants`, { method: 'PUT', data }),
  listUsers: () => request('/api/v1/multi-user/users'),
  assignSpace: (userId, data) => request(`/api/v1/multi-user/users/${userId}/spaces/assign`, { method: 'POST', data }),
}
