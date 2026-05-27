import { useWS } from '../utils/ws'

export const questionApi = {
  generate(payload, onEvent) {
    const ws = useWS()
    const base = (uni.getStorageSync('api_base') || 'http://localhost:8001').replace(/^http/, 'ws')
    const taskWs = uni.connectSocket({ url: `${base}/api/v1/question/generate` })
    taskWs.onMessage((res) => {
      try {
        const msg = JSON.parse(res.data)
        onEvent(msg)
      } catch (e) {}
    })
    taskWs.onOpen(() => {
      taskWs.send({ data: JSON.stringify(payload) })
    })
    return taskWs
  },
  mimic(payload, onEvent) {
    const base = (uni.getStorageSync('api_base') || 'http://localhost:8001').replace(/^http/, 'ws')
    const taskWs = uni.connectSocket({ url: `${base}/api/v1/question/mimic` })
    taskWs.onMessage((res) => {
      try {
        const msg = JSON.parse(res.data)
        onEvent(msg)
      } catch (e) {}
    })
    taskWs.onOpen(() => {
      taskWs.send({ data: JSON.stringify(payload) })
    })
    return taskWs
  },
}
