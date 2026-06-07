<template>
  <view class="kb-page">
    <view class="kb-header">
      <text class="page-title">知识库</text>
      <u-button type="primary" size="small" shape="circle" @click="goCreate">新建</u-button>
    </view>
    <view v-if="loading" class="loading">
      <u-loading-icon />
    </view>
    <view v-else-if="list.length === 0" class="empty">
      <u-icon name="folder" size="80" color="#d1d5db" />
      <text>暂无知识库</text>
    </view>
    <view v-for="kb in list" :key="kb.name || kb.id" class="kb-card" @click="goDetail(kb.name || kb.id)">
      <KnowledgeCard :kb="kb" />
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
    goCreate() { uni.navigateTo({ url: '/pages/study/aidlearning/knowledge/create' }) },
    goDetail(name) { uni.navigateTo({ url: `/pages/study/aidlearning/knowledge/detail?name=${name}` }) },
  },
}
</script>

<style lang="scss" scoped>
.kb-page { padding: 30rpx; min-height: 100vh; }
.kb-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; }
.loading { display: flex; justify-content: center; padding: 100rpx 0; }
.empty { display: flex; flex-direction: column; align-items: center; padding: 100rpx 0; color: #9ca3af; font-size: 28rpx; }
.kb-card { margin-bottom: 20rpx; }
</style>
