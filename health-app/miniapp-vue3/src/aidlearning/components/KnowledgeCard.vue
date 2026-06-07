<template>
  <view class="kb-card">
    <view class="card-header">
      <u-icon name="folder" size="40" color="#4f46e5" />
      <view class="card-info">
        <text class="card-title">{{ kb.name || kb.id }}</text>
        <text class="card-desc">{{ kb.description || '暂无描述' }}</text>
      </view>
    </view>
    <view class="card-footer">
      <text class="stat">{{ kb.statistics?.total_files || 0 }} 文件</text>
      <u-tag :text="kb.status || 'ready'" :type="kb.status === 'ready' ? 'success' : 'warning'" plain size="mini" />
      <u-tag v-if="kb.is_default" text="默认" type="primary" plain size="mini" />
    </view>
  </view>
</template>

<script>
export default {
  props: {
    kb: { type: Object, default: () => ({}) },
  },
}
</script>

<style lang="scss" scoped>
.kb-card {
  background: #fff; border-radius: 16rpx; padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04);
}
.card-header { display: flex; align-items: center; gap: 20rpx; }
.card-info { flex: 1; }
.card-title { display: block; font-size: 30rpx; font-weight: 600; color: #1f2937; }
.card-desc { display: block; font-size: 24rpx; color: #9ca3af; margin-top: 6rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-footer { display: flex; align-items: center; gap: 12rpx; margin-top: 16rpx; padding-top: 16rpx; border-top: 1rpx solid #f3f4f6; }
.stat { font-size: 24rpx; color: #6b7280; }
</style>
