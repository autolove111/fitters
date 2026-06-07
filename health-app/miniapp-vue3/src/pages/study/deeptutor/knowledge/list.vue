<template>
  <view class="kb-page">
    <!-- 顶部渐变装饰 -->
    <view class="top-deco" />

    <view class="kb-header">
      <view class="header-left">
        <view class="header-accent" />
        <text class="page-title">知识库</text>
        <text class="page-count" v-if="list.length">{{ list.length }}</text>
      </view>
      <view class="btn-new" @click="goCreate">
        <u-icon name="plus" size="26" color="#ffffff" />
        <text>新建</text>
      </view>
    </view>

    <view v-if="loading" class="loading">
      <u-loading-icon size="48" color="#0ea5e9" />
      <text class="loading-text">加载中...</text>
    </view>

    <view v-else-if="list.length === 0" class="empty">
      <view class="empty-icon">
        <u-icon name="folder" size="64" color="#94a3b8" />
      </view>
      <text class="empty-title">还没有知识库</text>
      <text class="empty-desc">创建一个知识库，让 AI 助手更好地为你服务</text>
      <view class="empty-btn" @click="goCreate">
        <u-icon name="plus" size="24" color="#ffffff" />
        <text>创建知识库</text>
      </view>
    </view>

    <view v-else class="kb-list">
      <view
        v-for="kb in list"
        :key="kb.name || kb.id"
        class="kb-card"
        @click="goDetail(kb.name || kb.id)"
      >
        <KnowledgeCard :kb="kb" />
      </view>
    </view>
  </view>
</template>

<script>
import { knowledgeApi } from '../../api/knowledge'
import KnowledgeCard from '../../components/KnowledgeCard.vue'

export default {
  components: { KnowledgeCard },
  data() {
    return { list: [], loading: true }
  },
  onShow() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        const res = await knowledgeApi.list()
        this.list = Array.isArray(res) ? res : res.knowledge_bases || []
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    goCreate() { uni.navigateTo({ url: '/pages/study/deeptutor/knowledge/create' }) },
    goDetail(name) { uni.navigateTo({ url: `/pages/study/deeptutor/knowledge/detail?name=${name}` }) },
  },
}
</script>

<style lang="scss" scoped>
.kb-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f0f7ff 0%, #f8fbff 30%, #ffffff 100%);
  padding: 0 28rpx 40rpx;
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

.kb-header {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.page-count {
  font-size: 22rpx;
  font-weight: 600;
  color: #0ea5e9;
  background: rgba(14, 165, 233, 0.1);
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
}

.btn-new {
  display: flex;
  align-items: center;
  gap: 8rpx;
  height: 68rpx;
  padding: 0 28rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #0ea5e9, #14b8a6);
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 600;
  box-shadow: 0 12rpx 24rpx rgba(14, 165, 233, 0.25);
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
  padding: 160rpx 0;
}

.loading-text {
  font-size: 26rpx;
  color: #94a3b8;
}

.empty {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 180rpx 40rpx 0;
}

.empty-icon {
  width: 140rpx;
  height: 140rpx;
  border-radius: 44rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(20, 184, 166, 0.06));
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}

.empty-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12rpx;
}

.empty-desc {
  font-size: 26rpx;
  color: #94a3b8;
  text-align: center;
  line-height: 1.6;
  margin-bottom: 40rpx;
}

.empty-btn {
  display: flex;
  align-items: center;
  gap: 8rpx;
  height: 72rpx;
  padding: 0 36rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #0ea5e9, #14b8a6);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 600;
  box-shadow: 0 12rpx 24rpx rgba(14, 165, 233, 0.25);
}

.kb-list {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
</style>
