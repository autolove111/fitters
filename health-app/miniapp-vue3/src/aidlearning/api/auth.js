import { request } from '../utils/api'

export const authApi = {
  status: () => request('/api/v1/auth/status'),
  login: (data) => request('/api/v1/auth/login', { method: 'POST', data }),
  logout: () => request('/api/v1/auth/logout', { method: 'POST' }),
  register: (data) => request('/api/v1/auth/register', { method: 'POST', data }),
  isFirstUser: () => request('/api/v1/auth/is_first_user'),
  listUsers: () => request('/api/v1/auth/users'),
  createUser: (data) => request('/api/v1/auth/users', { method: 'POST', data }),
  deleteUser: (username) => request(`/api/v1/auth/users/${username}`, { method: 'DELETE' }),
  updateRole: (username, role) => request(`/api/v1/auth/users/${username}/role`, { method: 'PUT', data: { role } }),
}
