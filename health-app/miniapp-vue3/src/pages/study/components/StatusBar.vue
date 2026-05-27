<template>
  <view class="status-bar" :class="connected ? 'connected' : 'disconnected'">
    <view class="dot" />
    <text>{{ connected ? '已连接' : '未连接' }}</text>
  </view>
</template>

<script>
import { useWS } from '../utils/ws'

export default {
  data() {
    return { connected: false }
  },
  mounted() {
    const ws = useWS()
    this.connected = ws.isConnected
    ws.on('open', () => { this.connected = true })
    ws.on('close', () => { this.connected = false })
  },
}
</script>

<style lang="scss" scoped>
.status-bar {
  display: flex; align-items: center; gap: 8rpx;
  font-size: 22rpx; padding: 4rpx 16rpx; border-radius: 20rpx;
}
.status-bar.connected { color: #10b981; }
.status-bar.disconnected { color: #ef4444; }
.dot {
  width: 12rpx; height: 12rpx; border-radius: 50%;
}
.connected .dot { background: #10b981; }
.disconnected .dot { background: #ef4444; }
</style>
