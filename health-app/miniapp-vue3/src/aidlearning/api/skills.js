import { request } from '../utils/api'

export const skillsApi = {
  listTags: () => request('/api/v1/skills/tags/list'),
  createTag: (tag) => request('/api/v1/skills/tags/create', { method: 'POST', data: { tag } }),
  renameTag: (tag, data) => request(`/api/v1/skills/tags/${tag}`, { method: 'PUT', data }),
  deleteTag: (tag) => request(`/api/v1/skills/tags/${tag}`, { method: 'DELETE' }),
  list: () => request('/api/v1/skills/list'),
  get: (name) => request(`/api/v1/skills/${name}`),
  create: (data) => request('/api/v1/skills/create', { method: 'POST', data }),
  update: (name, data) => request(`/api/v1/skills/${name}`, { method: 'PUT', data }),
  delete: (name) => request(`/api/v1/skills/${name}`, { method: 'DELETE' }),
}
