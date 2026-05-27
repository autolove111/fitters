<template>
  <view class="composer">
    <view class="composer-row">
      <u-textarea v-model="text" :placeholder="placeholder" autoHeight maxlength="8000" :disabled="disabled" border="none" class="input" />
      <view class="send-btn" @click="$emit('send', text)">
        <u-icon :name="disabled ? 'close-circle' : 'send'" size="44" :color="disabled ? '#ef4444' : '#4f46e5'" />
      </view>
    </view>
    <slot name="options" />
  </view>
</template>

<script>
export default {
  props: {
    modelValue: { type: String, default: '' },
    placeholder: { type: String, default: '输入消息...' },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'send'],
  computed: {
    text: {
      get() { return this.modelValue },
      set(v) { this.$emit('update:modelValue', v) },
    },
  },
}
</script>

<style lang="scss" scoped>
.composer {
  background: #fff; padding: 20rpx 30rpx; border-top: 1rpx solid #e5e7eb;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
}
.composer-row { display: flex; align-items: flex-end; gap: 16rpx; }
.input { flex: 1; background: #f9fafb; border-radius: 20rpx; padding: 16rpx 24rpx; }
.send-btn { width: 80rpx; height: 80rpx; display: flex; align-items: center; justify-content: center; }
</style>
