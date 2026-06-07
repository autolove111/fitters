import { request } from '../utils/api'

export const sessionsApi = {
  list: (limit = 50, offset = 0) => request(`/api/v1/sessions?limit=${limit}&offset=${offset}`),
  get: (id) => request(`/api/v1/sessions/${id}`),
  updateTitle: (id, title) => request(`/api/v1/sessions/${id}`, { method: 'PATCH', data: { title } }),
  delete: (id) => request(`/api/v1/sessions/${id}`, { method: 'DELETE' }),
  updateBranch: (id, data) => request(`/api/v1/sessions/${id}/branch-selection`, { method: 'PUT', data }),
  deleteMessage: (sessionId, messageId) => request(`/api/v1/sessions/${sessionId}/messages/${messageId}`, { method: 'DELETE' }),
  recordQuiz: (sessionId, data) => request(`/api/v1/sessions/${sessionId}/quiz-results`, { method: 'POST', data }),
}
