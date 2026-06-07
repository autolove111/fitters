<template>
  <view class="session-page">
    <scroll-view scroll-y class="messages-area" :scroll-into-view="scrollTarget" scroll-with-animation>
      <view v-for="(msg, i) in messages" :key="i" :id="'msg-' + i">
        <ChatMessage :message="msg" />
      </view>
      <view id="msg-bottom" style="height: 20rpx;" />
    </scroll-view>
  </view>
</template>

<script>
import { useChatStore } from '../../store/chat'
import ChatMessage from '../../components/ChatMessage.vue'

export default {
  components: { ChatMessage },
  data() {
    return {
      chatStore: useChatStore(),
      scrollTarget: '',
    }
  },
  computed: {
    messages() { return this.chatStore.state.messages },
  },
  async onLoad(query) {
    if (query.id) {
      await this.chatStore.loadSession(query.id)
      this.scrollToBottom()
    }
  },
  methods: {
    scrollToBottom() {
      setTimeout(() => { this.scrollTarget = 'msg-bottom' }, 100)
    },
  },
}
</script>

<style lang="scss" scoped>
.session-page { display: flex; flex-direction: column; height: 100vh; background: #f5f6fa; }
.messages-area { flex: 1; padding: 20rpx; }
</style>
