<template>
  <view class="create-page">
    <view class="top-deco" />

    <view class="page-header">
      <view class="header-left">
        <view class="header-accent" />
        <text class="page-title">创建知识库</text>
      </view>
    </view>

    <view class="form-section">
      <view class="input-group">
        <text class="input-label">名称</text>
        <view class="input-wrap">
          <u-input v-model="name" placeholder="给知识库起个名字" border="none" :customStyle="{ color: '#0f172a' }" />
        </view>
      </view>

      <view class="input-group">
        <text class="input-label">文件</text>
        <view class="upload-area" @click="chooseFiles">
          <view class="upload-icon">
            <u-icon name="plus" size="40" color="#0ea5e9" />
          </view>
          <text class="upload-text">点击选择文件</text>
          <text class="upload-hint">支持 PDF、Word、TXT 等格式</text>
        </view>
      </view>

      <view v-if="selectedFiles.length" class="file-list">
        <view v-for="(f, i) in selectedFiles" :key="i" class="file-item">
          <view class="file-info">
            <u-icon name="file-text" size="28" color="#0ea5e9" />
            <text class="file-name">{{ f.name }}</text>
          </view>
          <u-icon name="close" size="26" color="#94a3b8" @click="removeFile(i)" />
        </view>
      </view>

      <view
        class="btn-create"
        :class="{ disabled: !name || selectedFiles.length === 0 || creating }"
        @click="handleCreate"
      >
        <u-loading-icon v-if="creating" size="28" color="#ffffff" />
        <text v-else>创建知识库</text>
      </view>
    </view>
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
      if (!this.name || this.selectedFiles.length === 0 || this.creating) return
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
.create-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f0f7ff 0%, #f8fbff 30%, #ffffff 100%);
  padding: 0 28rpx 60rpx;
  position: relative;
}

.top-deco {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 260rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(20, 184, 166, 0.06));
  border-radius: 0 0 60rpx 60rpx;
}

.page-header {
  position: relative;
  padding: 32rpx 0 28rpx;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.header-accent {
  width: 8rpx;
  height: 36rpx;
  border-radius: 4rpx;
  background: linear-gradient(180deg, #0ea5e9, #14b8a6);
}

.page-title {
  font-size: 38rpx;
  font-weight: 700;
  color: #0f172a;
}

.form-section {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 32rpx;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.input-label {
  font-size: 26rpx;
  font-weight: 600;
  color: #334155;
}

.input-wrap {
  background: #ffffff;
  border-radius: 20rpx;
  padding: 4rpx 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(15, 23, 42, 0.04);
  border: 1rpx solid rgba(14, 165, 233, 0.08);
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14rpx;
  padding: 60rpx 40rpx;
  border-radius: 24rpx;
  border: 2rpx dashed rgba(14, 165, 233, 0.25);
  background: rgba(14, 165, 233, 0.02);
}

.upload-icon {
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  background: rgba(14, 165, 233, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8rpx;
}

.upload-text {
  font-size: 28rpx;
  font-weight: 500;
  color: #334155;
}

.upload-hint {
  font-size: 24rpx;
  color: #94a3b8;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #ffffff;
  padding: 20rpx 24rpx;
  border-radius: 16rpx;
  box-shadow: 0 2rpx 12rpx rgba(15, 23, 42, 0.04);
  border: 1rpx solid rgba(14, 165, 233, 0.06);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 14rpx;
  min-width: 0;
}

.file-name {
  font-size: 26rpx;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-create {
  height: 88rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #0ea5e9, #14b8a6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 600;
  margin-top: 16rpx;
  box-shadow: 0 16rpx 32rpx rgba(14, 165, 233, 0.25);

  &.disabled {
    opacity: 0.5;
  }
}
</style>
