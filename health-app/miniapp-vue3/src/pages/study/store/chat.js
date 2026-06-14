import { reactive } from 'vue'
import { request } from '../utils/api'
import { useWS } from '../utils/ws'

const state = reactive({
  sessions: [],
  currentSessionId: '',
  messages: [],
  isStreaming: false,
  streamingContent: '',
  streamingThinking: '',
  pendingAssistantMessage: null,
  capability: 'chat',
  selectedTools: [],
  selectedKnowledgeBases: [],
  selectedModel: '',
})

let wsInitialized = false
let messageAddedForTurn = false // 标记当前轮次是否已添加消息

const initWS = () => {
  if (wsInitialized) return

  const ws = useWS()

  // 先移除所有旧监听器，防止重复注册
  ws.off('content')
  ws.off('thinking')
  ws.off('result')
  ws.off('done')
  ws.off('error')
  ws.off('session')

  ws.on('content', (msg) => {
    if (!state.isStreaming) return
    state.streamingContent += msg.content || ''
  })

  ws.on('thinking', (msg) => {
    if (!state.isStreaming) return
    state.streamingThinking += msg.content || ''
  })

  ws.on('result', (msg) => {
    if (msg.session_id) state.currentSessionId = msg.session_id
    if (msg.message && !messageAddedForTurn) {
      state.pendingAssistantMessage = msg.message
    }
  })

  ws.on('done', () => {
    // 如果不在流式状态或已添加过消息，跳过
    if (!state.isStreaming || messageAddedForTurn) return

    // 标记已添加消息
    messageAddedForTurn = true
    state.isStreaming = false

    // 优先使用流式内容
    if (state.streamingContent) {
      state.messages.push({
        role: 'assistant',
        content: state.streamingContent,
        thinking: state.streamingThinking || undefined,
      })
    } else if (state.pendingAssistantMessage) {
      state.messages.push(state.pendingAssistantMessage)
    }

    // 清空所有临时状态
    state.streamingContent = ''
    state.streamingThinking = ''
    state.pendingAssistantMessage = null
  })

  ws.on('error', (msg) => {
    state.isStreaming = false
    state.pendingAssistantMessage = null
    messageAddedForTurn = false
    if (msg.session_id) state.currentSessionId = msg.session_id
    uni.showToast({ title: msg.content || msg.message || '发生错误', icon: 'none' })
  })

  ws.on('session', (msg) => {
    const sessionId = msg.session_id || msg?.metadata?.session_id || msg?.session?.id
    if (sessionId) state.currentSessionId = sessionId
  })

  wsInitialized = true
}

const ensureConnected = () => {
  const ws = useWS()
  if (!ws.isConnected) {
    ws.connect()
  }
  initWS()
}

const loadSessions = async (limit = 50, offset = 0) => {
  const res = await request(`/api/v1/sessions?limit=${limit}&offset=${offset}`)
  state.sessions = res.sessions || res || []
  return state.sessions
}

const loadSession = async (sessionId) => {
  const res = await request(`/api/v1/sessions/${sessionId}`)
  state.currentSessionId = sessionId
  state.messages = res.messages || []
  return res
}

const sendMessage = (content, options = {}) => {
  ensureConnected()
  state.isStreaming = true
  state.streamingContent = ''
  state.streamingThinking = ''
  state.pendingAssistantMessage = null
  state.messages.push({ role: 'user', content })

  const ws = useWS()
  ws.startTurn({
    content,
    capability: state.capability,
    tools: state.selectedTools,
    knowledge_bases: state.selectedKnowledgeBases,
    model_id: state.selectedModel || undefined,
    session_id: state.currentSessionId || undefined,
    ...options,
  })
}

const cancelStreaming = () => {
  const ws = useWS()
  ws.cancelTurn()
  state.isStreaming = false
  state.pendingAssistantMessage = null
}

const submitUserReply = (answer) => {
  const ws = useWS()
  ws.submitUserReply(answer)
}

const renameSession = async (sessionId, title) => {
  await request(`/api/v1/sessions/${sessionId}`, {
    method: 'PATCH',
    data: { title },
  })
  const idx = state.sessions.findIndex((s) => s.id === sessionId)
  if (idx >= 0) state.sessions[idx].title = title
}

const deleteSession = async (sessionId) => {
  await request(`/api/v1/sessions/${sessionId}`, { method: 'DELETE' })
  state.sessions = state.sessions.filter((s) => s.id !== sessionId)
  if (state.currentSessionId === sessionId) {
    state.currentSessionId = ''
    state.messages = []
  }
}

const newSession = () => {
  state.currentSessionId = ''
  state.messages = []
  state.streamingContent = ''
  state.streamingThinking = ''
  state.pendingAssistantMessage = null
}

export const useChatStore = () => ({
  state,
  loadSessions,
  loadSession,
  sendMessage,
  cancelStreaming,
  submitUserReply,
  renameSession,
  deleteSession,
  newSession,
  ensureConnected,
})
