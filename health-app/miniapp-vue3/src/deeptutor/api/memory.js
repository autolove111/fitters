import { request } from '../utils/api'

export const memoryApi = {
  overview: () => request('/api/v1/memory/overview'),
  resolveEntry: (entryId) => request(`/api/v1/memory/resolve_entry/${entryId}`),
  backup: () => request('/api/v1/memory/backup'),
  getDoc: (layer, key) => request(`/api/v1/memory/doc/${layer}/${key}`),
  saveDoc: (layer, key, content) => request(`/api/v1/memory/doc/${layer}/${key}`, { method: 'PUT', data: { content } }),
  deleteEntry: (layer, key, entryId) => request(`/api/v1/memory/doc/${layer}/${key}/entry/${entryId}`, { method: 'DELETE' }),
  resetDoc: (layer, key) => request(`/api/v1/memory/doc/${layer}/${key}/reset`, { method: 'POST' }),
  getDocLines: (layer, key) => request(`/api/v1/memory/doc/${layer}/${key}/lines`),
  applyOps: (layer, key, data) => request(`/api/v1/memory/doc/${layer}/${key}/apply`, { method: 'POST', data }),
  startRun: (data) => request('/api/v1/memory/runs/start', { method: 'POST', data }),
  getRun: (runId) => request(`/api/v1/memory/runs/${runId}`),
  cancelRun: (runId) => request(`/api/v1/memory/runs/${runId}/cancel`, { method: 'POST' }),
  undoRun: (runId) => request(`/api/v1/memory/runs/${runId}/undo`, { method: 'POST' }),
  listRuns: (params = {}) => {
    const qs = Object.entries(params).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join('&')
    return request(`/api/v1/memory/runs${qs ? '?' + qs : ''}`)
  },
  getRunEvents: (runId, cursor = 0) => request(`/api/v1/memory/runs/${runId}/events?cursor=${cursor}`),
  getSettings: () => request('/api/v1/memory/settings'),
  saveSettings: (data) => request('/api/v1/memory/settings', { method: 'PUT', data }),
  trace: (surface, params = {}) => {
    const qs = Object.entries(params).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join('&')
    return request(`/api/v1/memory/trace/${surface}${qs ? '?' + qs : ''}`)
  },
  deleteTrace: (surface) => request(`/api/v1/memory/trace/${surface}`, { method: 'DELETE' }),
  deleteTraceDay: (surface, day) => request(`/api/v1/memory/trace/${surface}/day/${day}`, { method: 'DELETE' }),
  snapshot: (surface) => request(`/api/v1/memory/snapshot/${surface}`),
  refreshSnapshot: (surface) => request(`/api/v1/memory/snapshot/${surface}/refresh`, { method: 'POST' }),
  snapshotChanges: (surface) => request(`/api/v1/memory/snapshot/${surface}/changes`),
  clearSnapshotChanges: (surface) => request(`/api/v1/memory/snapshot/${surface}/changes`, { method: 'DELETE' }),
}
