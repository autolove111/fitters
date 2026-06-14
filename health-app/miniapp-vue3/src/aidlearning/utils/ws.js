import { getApiBase } from './api'

export class AidLearningWS {
  constructor() {
    this.socketTask = null
    this.listeners = {}
    this.isConnected = false
    this.isConnecting = false
    this.heartbeatTimer = null
    this.reconnectTimer = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.sequence = 0
    this.pendingMessages = []
    this.manualClose = false
  }

  connect() {
    if (this.isConnected || this.isConnecting) return

    this.manualClose = false
    this.isConnecting = true
    const base = getApiBase().replace(/^http/, 'ws')
    const url = `${base}/api/v1/ws`

    this.socketTask = uni.connectSocket({
      url,
      success: () => {},
      fail: (err) => console.error('[WS] connect fail:', err),
    })

    this.socketTask.onOpen(() => {
      console.log('[WS] connected')
      this.isConnected = true
      this.isConnecting = false
      this.reconnectAttempts = 0
      this._startHeartbeat()
      this._flushPending()
      this._emit('open')
    })

    this.socketTask.onMessage((res) => {
      try {
        const msg = JSON.parse(res.data)
        this._handleMessage(msg)
      } catch (e) {
        console.error('[WS] parse error:', e)
      }
    })

    this.socketTask.onClose(() => {
      console.log('[WS] closed')
      this.isConnected = false
      this.isConnecting = false
      this._stopHeartbeat()
      this._emit('close')
      if (!this.manualClose) {
        this._tryReconnect()
      }
    })

    this.socketTask.onError((err) => {
      console.error('[WS] error:', err)
      this.isConnecting = false
      this._emit('error', err)
    })
  }

  _handleMessage(msg) {
    const { type } = msg
    if (type === 'pong') return
    if (type === 'sequence') {
      this.sequence = msg.seq
      return
    }
    this._emit(type, msg)
    this._emit('message', msg)
  }

  send(data) {
    const payload = typeof data === 'string' ? data : JSON.stringify(data)
    if (!this.isConnected) {
      this.pendingMessages.push(payload)
      this.connect()
      return
    }
    this.socketTask.send({ data: payload })
  }

  startTurn(payload) {
    this.send({ type: 'start_turn', ...payload })
  }

  cancelTurn() {
    this.send({ type: 'cancel_turn' })
  }

  submitUserReply(answer) {
    this.send({ type: 'submit_user_reply', answer })
  }

  regenerate() {
    this.send({ type: 'regenerate' })
  }

  subscribeSession(sessionId) {
    this.send({ type: 'subscribe_session', session_id: sessionId })
  }

  unsubscribe() {
    this.send({ type: 'unsubscribe' })
  }

  on(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = []
    this.listeners[event].push(callback)
  }

  off(event, callback) {
    if (!this.listeners[event]) return
    this.listeners[event] = this.listeners[event].filter((cb) => cb !== callback)
  }

  _emit(event, data) {
    ;(this.listeners[event] || []).forEach((cb) => {
      try { cb(data) } catch (e) { console.error('[WS] listener error:', e) }
    })
  }

  _startHeartbeat() {
    this._stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'ping' })
    }, 30000)
  }

  _stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  _flushPending() {
    if (!this.isConnected || !this.pendingMessages.length) return
    const queue = [...this.pendingMessages]
    this.pendingMessages = []
    queue.forEach((payload) => {
      this.socketTask.send({ data: payload })
    })
  }

  _tryReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('[WS] max reconnect attempts reached')
      this._emit('reconnect_failed')
      return
    }
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000)
    this.reconnectAttempts++
    console.log(`[WS] reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    this.reconnectTimer = setTimeout(() => this.connect(), delay)
  }

  disconnect() {
    this._stopHeartbeat()
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.manualClose = true
    this.isConnecting = false
    this.reconnectAttempts = this.maxReconnectAttempts
    if (this.socketTask) {
      this.socketTask.close({})
    }
    this.isConnected = false
  }
}

let instance = null
export const useWS = () => {
  if (!instance) instance = new AidLearningWS()
  return instance
}
