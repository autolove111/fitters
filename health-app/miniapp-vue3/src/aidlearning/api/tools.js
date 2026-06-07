import { request } from '../utils/api'

export const toolsApi = {
  list: () => request('/api/v1/tools'),
}
