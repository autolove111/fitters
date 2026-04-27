<template>
  <view class="card">
    <view class="title">{{ title }}</view>
    <view v-if="stats" class="stats-row">
      <view v-if="stats.workoutMinutes !== undefined">
        🏃 运动 {{ stats.workoutMinutes }} / {{ stats.workoutTarget }} 分钟
      </view>
      <view v-if="stats.sleepHours !== undefined">
        😴 睡眠 {{ stats.sleepHours }} / {{ stats.sleepTarget }} 小时
      </view>
      <view v-if="stats.dietCalories !== undefined">
        🍚 饮食 {{ stats.dietCalories }} / {{ stats.dietTarget }} 千卡
      </view>
      <view v-if="stats.workoutTotal !== undefined">
        本周运动 {{ stats.workoutTotal }} 分钟
      </view>
      <view v-if="stats.workoutCount !== undefined">
        总运动 {{ stats.workoutCount }} 次 · {{ stats.workoutMinutes }} 分钟
      </view>
    </view>
    <view v-else class="empty">暂无数据</view>
  </view>
</template>

<script setup>
defineProps(['title', 'stats'])
</script>

<style scoped>
.card { background: #fff; border-radius: 20rpx; padding: 30rpx; box-shadow: 0 2rpx 10rpx rgba(0,0,0,0.05); }
.title { font-size: 34rpx; font-weight: bold; margin-bottom: 20rpx; }
.stats-row { font-size: 28rpx; color: #333; display: flex; flex-direction: column; gap: 12rpx; }
.empty { color: #999; font-size: 28rpx; }
</style>