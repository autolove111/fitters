<template>
  <view class="file-uploader">
    <view class="upload-btn" @click="chooseFile">
      <u-icon name="plus" size="48" color="#9ca3af" />
      <text>{{ label }}</text>
    </view>
    <view v-for="(f, i) in files" :key="i" class="file-item">
      <u-icon name="file-text" size="32" color="#6b7280" />
      <text class="file-name">{{ f.name }}</text>
      <u-icon name="close" size="28" color="#ef4444" @click="removeFile(i)" />
    </view>
  </view>
</template>

<script>
export default {
  props: {
    modelValue: { type: Array, default: () => [] },
    label: { type: String, default: '选择文件' },
    count: { type: Number, default: 9 },
  },
  emits: ['update:modelValue'],
  computed: {
    files: {
      get() { return this.modelValue },
      set(v) { this.$emit('update:modelValue', v) },
    },
  },
  methods: {
    chooseFile() {
      uni.chooseFile({
        count: this.count,
        success: (res) => {
          const newFiles = res.tempFiles.map((f) => ({
            path: f.path,
            name: f.name || f.path.split('/').pop(),
            size: f.size,
          }))
          this.files = [...this.files, ...newFiles]
        },
      })
    },
    removeFile(i) {
      const list = [...this.files]
      list.splice(i, 1)
      this.files = list
    },
  },
}
</script>

<style lang="scss" scoped>
.upload-btn {
  border: 2rpx dashed #d1d5db; border-radius: 16rpx; padding: 40rpx;
  display: flex; flex-direction: column; align-items: center; gap: 12rpx;
  color: #6b7280; font-size: 26rpx;
}
.file-item {
  display: flex; align-items: center; gap: 12rpx;
  background: #f9fafb; padding: 16rpx 20rpx; border-radius: 12rpx;
  margin-top: 12rpx;
}
.file-name { flex: 1; font-size: 26rpx; color: #374151; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
