<template>
  <view class="chat-page">
    <scroll-view scroll-y class="messages-area" :scroll-into-view="scrollTarget" scroll-with-animation>
      <view v-if="messages.length === 0" class="empty-chat">
        <u-icon name="chat" size="80" color="#d1d5db" />
        <text>Start a conversation with AidLearning</text>
      </view>
      <view v-for="(msg, index) in messages" :key="`${msg.role}-${index}`" :id="`msg-${index}`">
        <ChatMessage :message="msg" />
      </view>
      <view v-if="chatStore.state.isStreaming" class="streaming-row">
        <view class="streaming-bubble">
          <text>{{ chatStore.state.streamingContent || 'Thinking...' }}</text>
        </view>
      </view>
      <view id="msg-bottom" class="msg-bottom" />
    </scroll-view>

    <view class="composer">
      <view class="composer-row">
        <u-textarea
          v-model="inputText"
          placeholder="Type your message..."
          autoHeight
          maxlength="8000"
          :disabled="chatStore.state.isStreaming"
          border="none"
          class="composer-input"
        />
        <view class="send-btn" @click="handleSend">
          <u-icon
            :name="chatStore.state.isStreaming ? 'close-circle' : 'arrow-up'"
            size="44"
            :color="chatStore.state.isStreaming ? '#ef4444' : '#d89a3a'"
          />
        </view>
      </view>
    </view>
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
      inputText: '',
      scrollTarget: '',
    }
  },
  computed: {
    messages() {
      return this.chatStore.state.messages
    },
  },
  watch: {
    messages: {
      deep: true,
      handler() {
        this.scrollToBottom()
      },
    },
    'chatStore.state.streamingContent'() {
      this.scrollToBottom()
    },
  },
  onLoad() {
    this.chatStore.ensureConnected()
    this.scrollToBottom()
  },
  methods: {
    handleSend() {
      if (this.chatStore.state.isStreaming) {
        this.chatStore.cancelStreaming()
        return
      }
      const text = this.inputText.trim()
      if (!text) return
      this.chatStore.sendMessage(text)
      this.inputText = ''
      this.scrollToBottom()
    },
    scrollToBottom() {
      setTimeout(() => {
        this.scrollTarget = ''
        this.$nextTick(() => {
          this.scrollTarget = 'msg-bottom'
        })
      }, 50)
    },
  },
}
</script>

<style lang="scss" scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f6fa;
}

.messages-area {
  flex: 1;
  padding: 20rpx;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 200rpx 0;
  color: #9ca3af;
  font-size: 28rpx;
}

.streaming-row {
  display: flex;
  margin-bottom: 24rpx;
}

.streaming-bubble {
  max-width: 80%;
  background: #fff;
  padding: 24rpx 30rpx;
  border-radius: 20rpx;
  font-size: 28rpx;
  color: #1f2937;
  line-height: 1.6;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.msg-bottom {
  height: 20rpx;
}

.composer {
  background: #fff;
  padding: 20rpx 30rpx;
  border-top: 1rpx solid #e5e7eb;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
}

.composer-row {
  display: flex;
  align-items: flex-end;
  gap: 16rpx;
}

.composer-input {
  flex: 1;
  background: #f9fafb;
  border-radius: 20rpx;
  padding: 16rpx 24rpx;
}

.send-btn {
  width: 80rpx;
  height: 80rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
