<template>
  <view class="detail-page">
    <view class="top-deco" />

    <view v-if="loading" class="loading">
      <u-loading-icon size="48" color="#0ea5e9" />
      <text class="loading-text">加载中...</text>
    </view>

    <template v-else>
      <!-- 知识库信息卡片 -->
      <view class="info-card">
        <view class="info-header">
          <view class="info-icon">
            <u-icon name="folder" size="40" color="#0ea5e9" />
          </view>
          <view class="info-content">
            <text class="kb-name">{{ kb.name }}</text>
            <text class="kb-desc">{{ kb.description || '暂无描述' }}</text>
          </view>
        </view>
        <view class="info-stats">
          <view class="stat-block">
            <text class="stat-num">{{ kb.statistics?.total_files || 0 }}</text>
            <text class="stat-label">文件</text>
          </view>
          <view class="stat-divider" />
          <view class="stat-block">
            <view :class="['status-badge', kb.status === 'ready' ? 'badge-ready' : 'badge-processing']">
              <view class="badge-dot" />
              <text>{{ kb.status || 'ready' }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 文件列表 -->
      <view class="section-card">
        <view class="section-header">
          <view class="section-accent" />
          <text class="section-title">文件列表</text>
          <text class="section-count" v-if="files.length">{{ files.length }}</text>
        </view>

        <view v-if="files.length === 0" class="empty-files">
          <u-icon name="file-text" size="48" color="#cbd5e1" />
          <text>暂无文件</text>
        </view>

        <view v-else class="file-list">
          <view v-for="f in files" :key="f.filename || f" class="file-item">
            <view class="file-icon">
              <u-icon name="file-text" size="28" color="#0ea5e9" />
            </view>
            <text class="file-name">{{ f.filename || f }}</text>
          </view>
        </view>
      </view>

      <!-- 操作按钮 -->
      <view class="actions">
        <view class="btn btn-primary" @click="handleUpload">
          <u-icon name="upload" size="26" color="#ffffff" />
          <text>上传文件</text>
        </view>
        <view class="btn btn-outline" @click="handleReindex">
          <u-icon name="reload" size="26" color="#0ea5e9" />
          <text>重新索引</text>
        </view>
        <view class="btn btn-danger" @click="handleDelete">
          <u-icon name="trash" size="26" color="#ef4444" />
          <text>删除</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script>
import { knowledgeApi } from '../../api/knowledge'

export default {
  data() {
    return { name: '', kb: {}, files: [], loading: true }
  },
  onLoad(query) {
    this.name = query.name
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      try {
        const [kb, files] = await Promise.all([
          knowledgeApi.detail(this.name),
          knowledgeApi.files(this.name),
        ])
        this.kb = kb
        this.files = Array.isArray(files) ? files : files.files || []
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    handleUpload() {
      uni.chooseFile({
        count: 9,
        success: async (res) => {
          for (const path of res.tempFilePaths) {
            try {
              await knowledgeApi.upload(this.name, path)
            } catch (e) {
              uni.showToast({ title: '上传失败', icon: 'none' })
            }
          }
          uni.showToast({ title: '上传完成', icon: 'success' })
          this.load()
        },
      })
    },
    async handleReindex() {
      try {
        await knowledgeApi.reindex(this.name)
        uni.showToast({ title: '已开始重建索引', icon: 'success' })
      } catch (e) {
        uni.showToast({ title: '操作失败', icon: 'none' })
      }
    },
    async handleDelete() {
      uni.showModal({
        title: '确认删除',
        content: `确定删除知识库 "${this.name}"？`,
        success: async (res) => {
          if (res.confirm) {
            try {
              await knowledgeApi.delete(this.name)
              uni.showToast({ title: '已删除', icon: 'success' })
              uni.navigateBack()
            } catch (e) {
              uni.showToast({ title: '删除失败', icon: 'none' })
            }
          }
        },
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.detail-page {
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

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
  padding: 200rpx 0;
}

.loading-text {
  font-size: 26rpx;
  color: #94a3b8;
}

.info-card {
  position: relative;
  background: #ffffff;
  border-radius: 28rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 24rpx rgba(15, 23, 42, 0.05);
  border: 1rpx solid rgba(14, 165, 233, 0.06);
}

.info-header {
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
}

.info-icon {
  width: 80rpx;
  height: 80rpx;
  border-radius: 24rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(20, 184, 166, 0.08));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.info-content {
  flex: 1;
  min-width: 0;
}

.kb-name {
  display: block;
  font-size: 34rpx;
  font-weight: 700;
  color: #0f172a;
}

.kb-desc {
  display: block;
  font-size: 26rpx;
  color: #94a3b8;
  margin-top: 8rpx;
  line-height: 1.5;
}

.info-stats {
  display: flex;
  align-items: center;
  gap: 32rpx;
  margin-top: 28rpx;
  padding-top: 24rpx;
  border-top: 1rpx solid rgba(148, 163, 184, 0.1);
}

.stat-block {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.stat-num {
  font-size: 36rpx;
  font-weight: 700;
  color: #0ea5e9;
}

.stat-label {
  font-size: 24rpx;
  color: #64748b;
}

.stat-divider {
  width: 1rpx;
  height: 36rpx;
  background: rgba(148, 163, 184, 0.15);
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 8rpx;
  height: 48rpx;
  padding: 0 20rpx;
  border-radius: 999rpx;
  font-size: 24rpx;
  font-weight: 500;
}

.badge-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 50%;
}

.badge-ready {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
  .badge-dot { background: #22c55e; }
}

.badge-processing {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
  .badge-dot { background: #f59e0b; }
}

.section-card {
  position: relative;
  background: #ffffff;
  border-radius: 28rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 24rpx rgba(15, 23, 42, 0.05);
  border: 1rpx solid rgba(14, 165, 233, 0.06);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 24rpx;
}

.section-accent {
  width: 6rpx;
  height: 28rpx;
  border-radius: 3rpx;
  background: linear-gradient(180deg, #0ea5e9, #14b8a6);
}

.section-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #0f172a;
}

.section-count {
  font-size: 22rpx;
  font-weight: 600;
  color: #0ea5e9;
  background: rgba(14, 165, 233, 0.1);
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
}

.empty-files {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14rpx;
  padding: 60rpx 0;
  color: #94a3b8;
  font-size: 26rpx;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 18rpx 16rpx;
  border-radius: 14rpx;

  &:active {
    background: rgba(14, 165, 233, 0.04);
  }
}

.file-icon {
  width: 52rpx;
  height: 52rpx;
  border-radius: 14rpx;
  background: rgba(14, 165, 233, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.file-name {
  font-size: 28rpx;
  color: #334155;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.btn {
  height: 84rpx;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  font-size: 28rpx;
  font-weight: 600;
}

.btn-primary {
  background: linear-gradient(135deg, #0ea5e9, #14b8a6);
  color: #ffffff;
  box-shadow: 0 12rpx 24rpx rgba(14, 165, 233, 0.25);
}

.btn-outline {
  background: #ffffff;
  color: #0ea5e9;
  border: 2rpx solid rgba(14, 165, 233, 0.2);
}

.btn-danger {
  background: #ffffff;
  color: #ef4444;
  border: 2rpx solid rgba(239, 68, 68, 0.15);
}
</style>
