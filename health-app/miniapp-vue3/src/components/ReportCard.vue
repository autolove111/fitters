<template>
  <view class="card">
    <view class="title">📊 今日综合健康报告</view>
    <view v-if="report" class="score">
      健康指数：<text class="num">{{ report.score }}</text> 分
    </view>
    <view class="detail">{{ report?.details }}</view>
    <view class="advice">💡 建议：{{ advice }}</view>
  </view>
</template>

<script setup>
defineProps(['report', 'advice'])
</script>

<style scoped>
.card { background: #e6f7ff; border-radius: 20rpx; padding: 30rpx; }
.title { font-size: 34rpx; font-weight: bold; }
.score { font-size: 32rpx; margin: 20rpx 0; }
.num { font-size: 48rpx; color: #2c3e50; font-weight: bold; }
.detail, .advice { font-size: 28rpx; margin-top: 10rpx; color: #2c3e50; }
.advice { background: #fef9e6; padding: 20rpx; border-radius: 16rpx; margin-top: 20rpx; }
</style>