<template>
  <view class="skill-card">
    <view class="card-accent" />
    <view class="card-body">
      <view class="card-header">
        <view class="icon-wrap">
          <u-icon name="star" size="36" color="#f59e0b" />
        </view>
        <view class="card-info">
          <text class="card-title">{{ skill.name }}</text>
          <text class="card-desc">{{ skill.description || '暂无描述' }}</text>
        </view>
      </view>
      <view v-if="skill.tags && skill.tags.length" class="card-tags">
        <view v-for="tag in skill.tags" :key="tag" class="tag-item">
          <text>{{ tag }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  props: {
    skill: { type: Object, default: () => ({}) },
  },
}
</script>

<style lang="scss" scoped>
.skill-card {
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
  background: linear-gradient(180deg, #f59e0b, #fbbf24);
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
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(251, 191, 36, 0.08));
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

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 18rpx;
  padding-top: 18rpx;
  border-top: 1rpx solid rgba(148, 163, 184, 0.1);
}

.tag-item {
  height: 44rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  background: rgba(245, 158, 11, 0.08);
  color: #d97706;
  font-size: 22rpx;
  font-weight: 500;
  display: flex;
  align-items: center;
}
</style>
