<template>
  <view class="form-container">
    <uni-forms>
      <uni-forms-item label="日期">
        <uni-datetime-picker v-model="form.date" type="date" />
      </uni-forms-item>
      <uni-forms-item label="总睡眠时长（小时）">
        <input v-model.number="form.durationHours" type="digit" placeholder="例如 7.5" />
      </uni-forms-item>
      <uni-forms-item label="深睡时长（小时）">
        <input v-model.number="form.deepHours" type="digit" placeholder="例如 2.5" />
      </uni-forms-item>
      <button type="primary" @click="submit">保存睡眠记录</button>
    </uni-forms>
  </view>
</template>

<script setup>
import { reactive } from 'vue'
import { sleepApi } from '@/utils/api'

const form = reactive({
  date: new Date().toISOString().slice(0,10),
  durationHours: 8,
  deepHours: 2
})

async function submit() {
  if (!form.durationHours || form.durationHours <= 0) {
    return uni.showToast({ title: '请填写有效睡眠时长', icon: 'none' })
  }
  try {
    await sleepApi.add(form)
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