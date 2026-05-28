<template>
  <view class="kb-detail">
    <view v-if="loading" class="loading"><u-loading-icon /></view>
    <template v-else>
      <view class="info-card">
        <text class="kb-name">{{ kb.name }}</text>
        <text class="kb-desc">{{ kb.description || '暂无描述' }}</text>
        <view class="kb-stats">
          <text>文件数: {{ kb.statistics?.total_files || 0 }}</text>
          <text>状态: {{ kb.status || 'ready' }}</text>
        </view>
      </view>

      <view class="section">
        <text class="section-title">文件列表</text>
        <view v-for="f in files" :key="f.filename || f" class="file-item">
          <u-icon name="file-text" size="32" color="#6b7280" />
          <text class="file-name">{{ f.filename || f }}</text>
        </view>
        <view v-if="files.length === 0" class="empty"><text>暂无文件</text></view>
      </view>

      <view class="actions">
        <u-button type="primary" plain shape="circle" @click="handleUpload">上传文件</u-button>
        <u-button type="warning" plain shape="circle" @click="handleReindex">重新索引</u-button>
        <u-button type="error" plain shape="circle" @click="handleDelete">删除</u-button>
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
.kb-detail { padding: 30rpx; }
.loading { display: flex; justify-content: center; padding: 100rpx 0; }
.info-card {
  background: #fff; border-radius: 16rpx; padding: 30rpx; margin-bottom: 30rpx;
  .kb-name { display: block; font-size: 36rpx; font-weight: 700; color: #1f2937; }
  .kb-desc { display: block; font-size: 26rpx; color: #6b7280; margin-top: 12rpx; }
  .kb-stats { display: flex; gap: 30rpx; margin-top: 16rpx; font-size: 24rpx; color: #9ca3af; }
}
.section { background: #fff; border-radius: 16rpx; padding: 30rpx; margin-bottom: 30rpx; }
.section-title { font-size: 30rpx; font-weight: 600; display: block; margin-bottom: 20rpx; }
.file-item { display: flex; align-items: center; gap: 16rpx; padding: 16rpx 0; border-bottom: 1rpx solid #f3f4f6; }
.file-name { font-size: 28rpx; color: #374151; }
.empty { text-align: center; padding: 40rpx; color: #9ca3af; font-size: 26rpx; }
.actions { display: flex; flex-direction: column; gap: 20rpx; }
</style>
