<template>
  <view class="form-container">
    <uni-forms>
      <uni-forms-item label="日期">
        <uni-datetime-picker v-model="form.date" type="date" />
      </uni-forms-item>
      <uni-forms-item label="运动类型">
        <input v-model="form.type" placeholder="例如：跑步、游泳" />
      </uni-forms-item>
      <uni-forms-item label="时长（分钟）">
        <input v-model.number="form.durationMin" type="number" placeholder="分钟" />
      </uni-forms-item>
      <uni-forms-item label="消耗卡路里">
        <input v-model.number="form.calories" type="number" placeholder="千卡" />
      </uni-forms-item>
      <button type="primary" @click="submit">保存记录</button>
    </uni-forms>
  </view>
</template>

<script setup>
import { reactive } from 'vue'
import { workoutApi } from '@/utils/api'

const form = reactive({
  date: new Date().toISOString().slice(0,10),
  type: '',
  durationMin: 30,
  calories: 200
})

async function submit() {
  if (!form.type) return uni.showToast({ title: '请填写运动类型', icon: 'none' })
  try {
    await workoutApi.add(form)
    uni.showToast({ title: '添加成功' })
    setTimeout(() => uni.navigateBack(), 1500)
  } catch (e) {
    uni.showToast({ title: e.message, icon: 'error' })
  }
}
</script>

<style scoped>
.form-container { padding: 40rpx; }
</style>