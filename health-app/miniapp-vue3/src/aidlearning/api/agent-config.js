import { request } from '../utils/api'

export const agentConfigApi = {
  getAgents: () => request('/api/v1/agent-config/agents'),
  getAgent: (agentType) => request(`/api/v1/agent-config/agents/${agentType}`),
}
