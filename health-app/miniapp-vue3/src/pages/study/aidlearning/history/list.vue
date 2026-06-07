<template>
  <view class="history-page">
    <text class="page-title">聊天历史</text>
    <view v-if="loading" class="loading"><u-loading-icon /></view>
    <view v-else-if="sessions.length === 0" class="empty"><text>暂无历史会话</text></view>
    <view v-for="s in sessions" :key="s.id" class="session-item" @click="goSession(s.id)" @longpress="onLongPress(s)">
      <view class="session-info">
        <text class="session-title">{{ s.title || '新对话' }}</text>
        <text class="session-time">{{ formatTime(s.updated_at) }}</text>
      </view>
      <u-icon name="arrow-right" size="28" color="#d1d5db" />
    </view>
  </view>
</template>

<script>
import { useChatStore } from '../../store/chat'
import dayjs from 'dayjs'

export default {
  data() {
    return { sessions: [], loading: true, chatStore: useChatStore() }
  },
  onShow() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        this.sessions = await this.chatStore.loadSessions(100, 0)
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    formatTime(t) { return t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '' },
    goSession(id) { uni.navigateTo({ url: `/pages/study/aidlearning/chat/session?id=${id}` }) },
    onLongPress(s) {
      uni.showActionSheet({
        itemList: ['重命名', '删除'],
        success: async (res) => {
          if (res.tapIndex === 0) {
            uni.showModal({
              title: '重命名',
              editable: true,
              placeholderText: s.title || '',
              success: async (r) => {
                if (r.confirm && r.content) {
                  await this.chatStore.renameSession(s.id, r.content)
                  this.load()
                }
              },
            })
          } else if (res.tapIndex === 1) {
            await this.chatStore.deleteSession(s.id)
            this.load()
          }
        },
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.history-page { padding: 30rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; display: block; margin-bottom: 30rpx; }
.loading { display: flex; justify-content: center; padding: 100rpx 0; }
.empty { text-align: center; padding: 100rpx 0; color: #9ca3af; }
.session-item {
  background: #fff; border-radius: 16rpx; padding: 24rpx 30rpx; margin-bottom: 16rpx;
  display: flex; align-items: center; justify-content: space-between;
  .session-info { flex: 1; }
  .session-title { display: block; font-size: 28rpx; color: #1f2937; font-weight: 500; }
  .session-time { display: block; font-size: 24rpx; color: #9ca3af; margin-top: 8rpx; }
}
</style>
