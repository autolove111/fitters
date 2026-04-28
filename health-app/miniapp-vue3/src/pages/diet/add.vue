<template>
  <view class="form-container">
    <uni-forms>
      <uni-forms-item label="日期">
        <uni-datetime-picker v-model="form.date" type="date" />
      </uni-forms-item>
      <uni-forms-item label="食物名称">
        <input v-model="form.foodName" placeholder="例如 苹果、鸡胸肉" />
      </uni-forms-item>
      <uni-forms-item label="热量（千卡）">
        <input v-model.number="form.calories" type="number" placeholder="千卡" />
      </uni-forms-item>
      <button type="primary" @click="submit">保存饮食记录</button>
    </uni-forms>
  </view>
</template>

<script setup>
import { reactive } from 'vue'
import { dietApi } from '@/utils/api'

const form = reactive({
  date: new Date().toISOString().slice(0,10),
  foodName: '',
  calories: 300
})

async function submit() {
  if (!form.foodName) {
    return uni.showToast({ title: '请填写食物名称', icon: 'none' })
  }
  if (!form.calories || form.calories <= 0) {
    return uni.showToast({ title: '请填写有效热量', icon: 'none' })
  }
  try {
    await dietApi.add(form)
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