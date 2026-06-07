<template>
  <view class="kb-card">
    <view class="card-accent" />
    <view class="card-body">
      <view class="card-header">
        <view class="icon-wrap">
          <u-icon name="folder" size="36" color="#0ea5e9" />
        </view>
        <view class="card-info">
          <text class="card-title">{{ kb.name || kb.id }}</text>
          <text class="card-desc">{{ kb.description || '暂无描述' }}</text>
        </view>
      </view>
      <view class="card-footer">
        <view class="stat-item">
          <u-icon name="file-text" size="20" color="#94a3b8" />
          <text class="stat">{{ kb.statistics?.total_files || 0 }} 文件</text>
        </view>
        <view class="tag-group">
          <view :class="['status-tag', statusClass]">
            <view class="status-dot" />
            <text>{{ kb.status || 'ready' }}</text>
          </view>
          <view v-if="kb.is_default" class="default-tag">
            <text>默认</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  props: {
    kb: { type: Object, default: () => ({}) },
  },
  computed: {
    statusClass() {
      if (this.kb.status === 'ready') return 'status-ready'
      if (this.kb.status === 'processing') return 'status-processing'
      return 'status-default'
    },
  },
}
</script>

<style lang="scss" scoped>
.kb-card {
  display: flex;
  background: #ffffff;
  border-radius: 24rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 20rpx rgba(15, 23, 42, 0.05);
  border: 1rpx solid rgba(14, 165, 233, 0.06);
}

.card-accent {
  width: 8rpx;
  flex-shrink: 0;
  background: linear-gradient(180deg, #0ea5e9, #14b8a6);
}

.card-body {
  flex: 1;
  padding: 28rpx 28rpx 24rpx;
  min-width: 0;
}

.card-header {
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
}

.icon-wrap {
  width: 72rpx;
  height: 72rpx;
  border-radius: 22rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(20, 184, 166, 0.08));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.card-info {
  flex: 1;
  min-width: 0;
}

.card-title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.4;
}

.card-desc {
  display: block;
  font-size: 24rpx;
  color: #94a3b8;
  margin-top: 6rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid rgba(148, 163, 184, 0.1);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.stat {
  font-size: 24rpx;
  color: #64748b;
}

.tag-group {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.status-tag {
  display: flex;
  align-items: center;
  gap: 8rpx;
  height: 44rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  font-size: 22rpx;
  font-weight: 500;
}

.status-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 50%;
}

.status-ready {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
  .status-dot { background: #22c55e; }
}

.status-processing {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
  .status-dot { background: #f59e0b; }
}

.status-default {
  background: rgba(148, 163, 184, 0.1);
  color: #64748b;
  .status-dot { background: #94a3b8; }
}

.default-tag {
  height: 44rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(20, 184, 166, 0.1));
  color: #0ea5e9;
  font-size: 22rpx;
  font-weight: 500;
  display: flex;
  align-items: center;
}
</style>
