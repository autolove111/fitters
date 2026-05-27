<template>
  <view class="memory-page">
    <text class="page-title">记忆系统</text>
    <view v-if="loading" class="loading"><u-loading-icon /></view>
    <template v-else>
      <view v-for="(doc, key) in docs" :key="key" class="doc-card" @click="goDoc(doc)">
        <text class="doc-key">{{ key }}</text>
        <text class="doc-layer">{{ doc.layer || 'L2' }}</text>
        <u-icon name="arrow-right" size="28" color="#9ca3af" />
      </view>
      <view v-if="Object.keys(docs).length === 0" class="empty"><text>暂无记忆文档</text></view>
    </template>
  </view>
</template>

<script>
import { memoryApi } from '../../api/memory'

export default {
  data() {
    return { docs: {}, loading: true }
  },
  onShow() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        const res = await memoryApi.overview()
        this.docs = res.documents || res || {}
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    goDoc(doc) {
      uni.navigateTo({ url: `/pages/study/deeptutor/memory/doc?layer=${doc.layer || 'L2'}&key=${doc.key || doc.name || ''}` })
    },
  },
}
</script>

<style lang="scss" scoped>
.memory-page { padding: 30rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; display: block; margin-bottom: 30rpx; }
.loading { display: flex; justify-content: center; padding: 100rpx 0; }
.doc-card {
  background: #fff; border-radius: 16rpx; padding: 30rpx; margin-bottom: 16rpx;
  display: flex; align-items: center; gap: 16rpx;
  .doc-key { flex: 1; font-size: 30rpx; font-weight: 600; color: #1f2937; }
  .doc-layer { font-size: 24rpx; color: #6b7280; background: #f3f4f6; padding: 4rpx 16rpx; border-radius: 8rpx; }
}
.empty { text-align: center; padding: 100rpx 0; color: #9ca3af; }
</style>
