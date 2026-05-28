<template>
  <view class="status-page">
    <text class="page-title">系统状态</text>
    <view v-if="loading" class="loading"><u-loading-icon /></view>
    <template v-else>
      <view class="status-card">
        <view class="status-row">
          <text>后端</text>
          <u-tag :text="status?.backend?.status || 'unknown'" :type="status?.backend?.status === 'ok' ? 'success' : 'error'" plain size="mini" />
        </view>
        <view class="status-row">
          <text>LLM</text>
          <u-tag :text="status?.llm?.status || 'unknown'" :type="status?.llm?.status === 'ok' ? 'success' : 'error'" plain size="mini" />
        </view>
        <view class="status-row">
          <text>Embeddings</text>
          <u-tag :text="status?.embeddings?.status || 'unknown'" :type="status?.embeddings?.status === 'ok' ? 'success' : 'error'" plain size="mini" />
        </view>
        <view class="status-row">
          <text>Search</text>
          <u-tag :text="status?.search?.status || 'unknown'" :type="status?.search?.status === 'ok' ? 'success' : 'error'" plain size="mini" />
        </view>
      </view>
      <view class="actions">
        <u-button type="primary" plain shape="circle" @click="testLLM">测试 LLM</u-button>
        <u-button type="primary" plain shape="circle" @click="testEmbeddings">测试 Embeddings</u-button>
        <u-button type="primary" plain shape="circle" @click="testSearch">测试 Search</u-button>
      </view>
      <view v-if="testResult" class="test-result">
        <u-tag :text="testResult.success ? '成功' : '失败'" :type="testResult.success ? 'success' : 'error'" />
        <text>{{ testResult.message || testResult.error }}</text>
      </view>
    </template>
  </view>
</template>

<script>
import { systemApi } from '../../api/system'

export default {
  data() { return { status: null, loading: true, testResult: null } },
  onShow() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try { this.status = await systemApi.status() } catch (e) {}
      this.loading = false
    },
    async testLLM() { this.testResult = await systemApi.testLLM({}).catch((e) => ({ success: false, error: e.message })) },
    async testEmbeddings() { this.testResult = await systemApi.testEmbeddings({}).catch((e) => ({ success: false, error: e.message })) },
    async testSearch() { this.testResult = await systemApi.testSearch({}).catch((e) => ({ success: false, error: e.message })) },
  },
}
</script>

<style lang="scss" scoped>
.status-page { padding: 30rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; display: block; margin-bottom: 30rpx; }
.loading { display: flex; justify-content: center; padding: 100rpx 0; }
.status-card { background: #fff; border-radius: 16rpx; padding: 10rpx 30rpx; margin-bottom: 30rpx; }
.status-row { display: flex; justify-content: space-between; align-items: center; padding: 24rpx 0; border-bottom: 1rpx solid #f3f4f6; font-size: 28rpx; &:last-child { border-bottom: none; } }
.actions { display: flex; flex-direction: column; gap: 16rpx; }
.test-result { background: #fff; border-radius: 16rpx; padding: 24rpx; margin-top: 24rpx; display: flex; align-items: center; gap: 16rpx; font-size: 26rpx; }
</style>
