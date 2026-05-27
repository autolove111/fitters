<template>
  <view :class="['chat-msg', message.role]">
    <view v-if="message.role === 'user'" class="user-bubble">
      <text>{{ message.content }}</text>
    </view>
    <view v-else class="assistant-bubble">
      <view v-if="message.thinking" class="thinking-block" @click="showThinking = !showThinking">
        <text class="thinking-label">思考过程</text>
        <view v-if="showThinking" class="thinking-content">
          <text>{{ message.thinking }}</text>
        </view>
      </view>
      <view class="content">
        <text>{{ message.content }}</text>
      </view>
      <view v-if="message.tool_calls && message.tool_calls.length" class="tool-calls">
        <view v-for="(tc, i) in message.tool_calls" :key="i" class="tool-call">
          <u-icon name="setting" size="24" color="#6b7280" />
          <text>{{ tc.name || tc.function?.name || 'tool' }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  props: {
    message: { type: Object, required: true },
  },
  data() {
    return { showThinking: false }
  },
}
</script>

<style lang="scss" scoped>
.chat-msg { margin-bottom: 24rpx; display: flex; }
.chat-msg.user { justify-content: flex-end; }
.chat-msg.assistant { justify-content: flex-start; }

.user-bubble {
  max-width: 80%; background: #4f46e5; color: #fff; padding: 24rpx 30rpx;
  border-radius: 20rpx 20rpx 4rpx 20rpx; font-size: 28rpx; line-height: 1.6;
}
.assistant-bubble {
  max-width: 85%; background: #fff; padding: 24rpx 30rpx;
  border-radius: 20rpx 20rpx 20rpx 4rpx; font-size: 28rpx; color: #1f2937; line-height: 1.6;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04);
}
.thinking-block {
  background: #f9fafb; border-radius: 12rpx; padding: 16rpx; margin-bottom: 16rpx;
  border-left: 4rpx solid #a5b4fc;
}
.thinking-label { font-size: 24rpx; color: #6366f1; font-weight: 500; display: block; margin-bottom: 8rpx; }
.thinking-content { font-size: 24rpx; color: #6b7280; line-height: 1.5; }
.tool-calls { margin-top: 16rpx; display: flex; flex-wrap: wrap; gap: 8rpx; }
.tool-call {
  display: flex; align-items: center; gap: 6rpx;
  background: #f3f4f6; padding: 6rpx 16rpx; border-radius: 8rpx;
  font-size: 22rpx; color: #6b7280;
}
</style>
