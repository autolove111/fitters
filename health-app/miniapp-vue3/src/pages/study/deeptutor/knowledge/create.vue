<template>
  <view class="create-kb">
    <text class="page-title">创建知识库</text>
    <u-input v-model="name" placeholder="知识库名称" border="surround" shape="circle" />
    <view class="upload-area" @click="chooseFiles">
      <u-icon name="plus" size="60" color="#9ca3af" />
      <text>点击选择文件</text>
      <text class="upload-hint">支持 PDF、Word、TXT 等格式</text>
    </view>
    <view v-for="(f, i) in selectedFiles" :key="i" class="file-item">
      <text>{{ f.name }}</text>
      <u-icon name="close" size="28" color="#ef4444" @click="removeFile(i)" />
    </view>
    <u-button type="primary" shape="circle" :loading="creating" :disabled="!name || selectedFiles.length === 0" @click="handleCreate">创建</u-button>
  </view>
</template>

<script>
import { knowledgeApi } from '../../api/knowledge'

export default {
  data() {
    return { name: '', selectedFiles: [], creating: false }
  },
  methods: {
    chooseFiles() {
      uni.chooseFile({
        count: 20,
        success: (res) => {
          res.tempFiles.forEach((f) => {
            this.selectedFiles.push({ path: f.path, name: f.name || f.path.split('/').pop() })
          })
        },
      })
    },
    removeFile(i) { this.selectedFiles.splice(i, 1) },
    async handleCreate() {
      this.creating = true
      try {
        await knowledgeApi.create(this.name, this.selectedFiles[0].path)
        uni.showToast({ title: '创建成功', icon: 'success' })
        setTimeout(() => uni.navigateBack(), 1000)
      } catch (e) {
        uni.showToast({ title: e.message || '创建失败', icon: 'none' })
      } finally {
        this.creating = false
      }
    },
  },
}
</script>

<style lang="scss" scoped>
.create-kb { padding: 30rpx; display: flex; flex-direction: column; gap: 24rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; margin-bottom: 10rpx; }
.upload-area {
  border: 2rpx dashed #d1d5db; border-radius: 16rpx; padding: 60rpx;
  display: flex; flex-direction: column; align-items: center; gap: 16rpx; color: #6b7280;
  .upload-hint { font-size: 24rpx; color: #9ca3af; }
}
.file-item {
  display: flex; justify-content: space-between; align-items: center;
  background: #f9fafb; padding: 16rpx 24rpx; border-radius: 12rpx;
  font-size: 26rpx; color: #374151;
}
</style>
