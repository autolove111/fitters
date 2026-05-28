<template>
  <view class="session-list">
    <view v-for="s in sessions" :key="s.id" class="session-item" @click="$emit('select', s)" @longpress="$emit('longpress', s)">
      <view class="session-info">
        <text class="session-title">{{ s.title || '新对话' }}</text>
        <text class="session-time">{{ formatTime(s.updated_at) }}</text>
      </view>
      <u-icon name="arrow-right" size="24" color="#d1d5db" />
    </view>
    <view v-if="sessions.length === 0" class="empty"><text>暂无会话</text></view>
  </view>
</template>

<script>
import dayjs from 'dayjs'

export default {
  props: {
    sessions: { type: Array, default: () => [] },
  },
  emits: ['select', 'longpress'],
  methods: {
    formatTime(t) { return t ? dayjs(t).format('MM-DD HH:mm') : '' },
  },
}
</script>

<style lang="scss" scoped>
.session-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 24rpx 0; border-bottom: 1rpx solid #f3f4f6;
}
.session-info { flex: 1; }
.session-title { display: block; font-size: 28rpx; color: #1f2937; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-time { display: block; font-size: 24rpx; color: #9ca3af; margin-top: 6rpx; }
.empty { text-align: center; padding: 60rpx 0; color: #9ca3af; font-size: 26rpx; }
</style>
