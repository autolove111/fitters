import { request } from '../utils/api'

export const systemApi = {
  runtimeTopology: () => request('/api/v1/system/runtime-topology'),
  status: () => request('/api/v1/system/status'),
  testLLM: (data) => request('/api/v1/system/test/llm', { method: 'POST', data }),
  testEmbeddings: (data) => request('/api/v1/system/test/embeddings', { method: 'POST', data }),
  testSearch: (data) => request('/api/v1/system/test/search', { method: 'POST', data }),
}
