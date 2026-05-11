<template>
  <view class="form-container">
    <uni-forms 
      ref="formRef" 
      :model="form" 
      :rules="rules"
      label-width="140"
    >
      <uni-forms-item label="日期" name="date">
        <uni-datetime-picker 
          v-model="form.date" 
          type="date" 
          :end="today" 
          placeholder="请选择日期"
        />
      </uni-forms-item>
      
      <uni-forms-item label="总睡眠时长（小时）" name="durationHours">
        <input 
          v-model.number="form.durationHours" 
          type="digit" 
          placeholder="例如 7.5"
          @blur="validateDeepHoursRange"
        />
      </uni-forms-item>
      
      <uni-forms-item label="深睡时长（小时）" name="deepHours">
        <input 
          v-model.number="form.deepHours" 
          type="digit" 
          placeholder="例如 2.5"
          @blur="validateDeepHoursRange"
        />
        <text class="tip">深睡时长应≤总时长</text>
      </uni-forms-item>
      
      <button 
        type="primary" 
        @click="submit" 
        :disabled="submitting"
        :loading="submitting"
      >
        {{ submitting ? '保存中...' : '保存睡眠记录' }}
      </button>
    </uni-forms>
  </view>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { sleepApi } from '@/utils/api'

// ---------- 工具函数 ----------
// 获取本地日期字符串 (yyyy-mm-dd)
const getLocalDateString = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// ---------- 常量 ----------
const MAX_SLEEP_HOURS = 24
const TODAY = getLocalDateString(new Date())

// ---------- 表单数据 ----------
const form = reactive({
  date: TODAY,
  durationHours: 8,    // 默认8小时
  deepHours: 2         // 默认2小时
})

// ---------- 表单校验规则 (uni-forms 标准) ----------
const rules = {
  date: {
    required: true,
    errorMessage: '请选择日期'
  },
  durationHours: {
    required: true,
    type: 'number',
    validator: (rule, value, callback) => {
      if (value === undefined || value === null || value === '') {
        callback('请填写总睡眠时长')
      } else if (typeof value !== 'number' || isNaN(value)) {
        callback('总睡眠时长必须是数字')
      } else if (value <= 0) {
        callback('总睡眠时长必须大于0')
      } else if (value > MAX_SLEEP_HOURS) {
        callback(`总睡眠时长不能超过${MAX_SLEEP_HOURS}小时`)
      } else {
        callback()
      }
    }
  },
  deepHours: {
    required: true,
    type: 'number',
    validator: (rule, value, callback) => {
      if (value === undefined || value === null || value === '') {
        callback('请填写深睡时长')
      } else if (typeof value !== 'number' || isNaN(value)) {
        callback('深睡时长必须是数字')
      } else if (value < 0) {
        callback('深睡时长不能为负数')
      } else if (value > form.durationHours) {
        callback(`深睡时长不能超过总睡眠时长（${form.durationHours}小时）`)
      } else {
        callback()
      }
    }
  }
}

// ---------- 辅助校验：自动修正深睡时长 ----------
const validateDeepHoursRange = () => {
  if (form.durationHours > 0 && form.deepHours > form.durationHours) {
    form.deepHours = form.durationHours
    uni.showToast({ 
      title: `深睡时长已自动调整为${form.durationHours}小时`, 
      icon: 'none',
      duration: 1500
    })
  }
}

// ---------- UI 状态 ----------
const submitting = ref(false)
const formRef = ref(null)

// ---------- 提交方法 ----------
async function submit() {
  // 防重复提交
  if (submitting.value) return
  
  // 触发表单校验
  return new Promise((resolve, reject) => {
    javascript
      formRef.value.validate(async (errors, field) => {
  if (errors) {
    const firstError = Object.values(errors)[0]?.message || '请正确填写表单'
    uni.showToast({ title: firstError, icon: 'none' })
    return reject(new Error(firstError))
  }
  // 校验通过后的代码保持不变...
})
      
      submitting.value = true
      uni.showLoading({ title: '保存中...', mask: true })
      
      try {
        // 调用 API
        await sleepApi.add({
          date: form.date,
          durationHours: form.durationHours,
          deepHours: form.deepHours
        })
        
        uni.hideLoading()
        uni.showToast({ title: '添加成功', icon: 'success' })
        
        setTimeout(() => {
          uni.navigateBack()
        }, 1500)
        
        resolve()
      } catch (err) {
        uni.hideLoading()
        const errorMsg = err?.message || err?.errMsg || '网络异常，保存失败'
        uni.showToast({ title: errorMsg, icon: 'error', duration: 2000 })
        reject(err)
      } finally {
        submitting.value = false
      }
    })
  }

</script>

<style scoped>
.form-container {
  padding: 40rpx;
}

.tip {
  font-size: 24rpx;
  color: #999;
  margin-top: 8rpx;
  display: block;
}

button[disabled] {
  opacity: 0.6;
}
</style>