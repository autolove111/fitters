<template>
  <view class="skill-card">
    <view class="card-header">
      <u-icon name="star" size="40" color="#f59e0b" />
      <view class="card-info">
        <text class="card-title">{{ skill.name }}</text>
        <text class="card-desc">{{ skill.description || '暂无描述' }}</text>
      </view>
    </view>
    <view v-if="skill.tags && skill.tags.length" class="card-tags">
      <u-tag v-for="tag in skill.tags" :key="tag" :text="tag" plain size="mini" type="info" />
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
  background: #fff; border-radius: 16rpx; padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04);
}
.card-header { display: flex; align-items: center; gap: 20rpx; }
.card-info { flex: 1; }
.card-title { display: block; font-size: 30rpx; font-weight: 600; color: #1f2937; }
.card-desc { display: block; font-size: 24rpx; color: #9ca3af; margin-top: 6rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-tags { display: flex; flex-wrap: wrap; gap: 8rpx; margin-top: 16rpx; }
</style>
