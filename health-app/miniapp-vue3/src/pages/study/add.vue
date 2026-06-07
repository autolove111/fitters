<template>
  <view class="add-container">
    <view class="page-header">
      <text class="page-title">添加学习计划</text>
      <text class="page-note">填写计划内容与时间后，提交到后端保存。</text>
    </view>

    <view class="form-card">
      <view class="field">
        <text class="label">计划内容</text>
        <textarea
          class="textarea"
          v-model="content"
          placeholder="请输入学习内容，例如：阅读第2章理论"
          placeholder-class="placeholder"
          auto-height
          maxlength="200"
        />
      </view>

      <view class="field-row">
        <view class="field small-field">
          <text class="label">开始时间</text>
          <input
            class="input"
            v-model="start"
            placeholder="2026-05-26 09:00"
            placeholder-class="placeholder"
          />
        </view>
        <view class="field small-field">
          <text class="label">结束时间</text>
          <input
            class="input"
            v-model="end"
            placeholder="2026-05-26 10:00"
            placeholder-class="placeholder"
          />
        </view>
      </view>

      <view class="material-section">
        <view class="material-header" @click="toggleMaterial">
          <text class="label" style="margin-bottom:0">学习资料（可选）</text>
          <text class="material-toggle">{{ showMaterial ? '收起' : '添加学习资料' }}</text>
        </view>
        <view v-if="showMaterial" class="material-body">
          <FileUploader v-model="selectedFiles" label="选择学习资料文件" :count="9" />
        </view>
      </view>

      <button class="submit-btn" :loading="submitting" @click="submitPlan">
        {{ submitting ? submitText : '提交学习计划' }}
      </button>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { studyApi } from '@/utils/api'
import { knowledgeApi } from '@/pages/study/api/knowledge'
import FileUploader from '@/pages/study/components/FileUploader.vue'

const content = ref('')
const start = ref('')
const end = ref('')
const showMaterial = ref(false)
const selectedFiles = ref([])
const submitting = ref(false)
const submitText = ref('提交中...')

function toggleMaterial() {
  showMaterial.value = !showMaterial.value
}

async function submitPlan() {
  if (!content.value.trim()) {
    uni.showToast({ title: '请填写计划内容', icon: 'none' })
    return
  }
  if (!start.value.trim() || !end.value.trim()) {
    uni.showToast({ title: '请填写开始和结束时间', icon: 'none' })
    return
  }

  submitting.value = true
  try {
    // 1. 保存学习计划
    submitText.value = '保存计划中...'
    await studyApi.add({ content: content.value, start: start.value, end: end.value })

    // 2. 如果有学习资料，上传到 AidLearning 知识库
    if (selectedFiles.value.length > 0) {
      const kbName = '计划-' + content.value.trim().substring(0, 20)
      submitText.value = `上传资料到知识库「${kbName}」...`

      try {
        // 用第一个文件创建知识库
        await knowledgeApi.create(kbName, selectedFiles.value[0].path)

        // 剩余文件追加上传
        for (let i = 1; i < selectedFiles.value.length; i++) {
          submitText.value = `上传第 ${i + 1}/${selectedFiles.value.length} 个文件...`
          await knowledgeApi.upload(kbName, selectedFiles.value[i].path)
        }

        uni.showToast({ title: '计划已保存，资料已上传', icon: 'success', duration: 2000 })
      } catch (uploadErr) {
        console.warn('知识库上传失败：', uploadErr)
        uni.showToast({ title: '计划已保存，但资料上传失败', icon: 'none', duration: 2000 })
      }
    } else {
      uni.showToast({ title: '学习计划已保存', icon: 'success' })
    }

    uni.navigateBack()
  } catch (err) {
    uni.showToast({ title: err.message || '提交失败，请稍后重试', icon: 'none' })
  } finally {
    submitting.value = false
    submitText.value = '提交中...'
  }
}
</script>

<style scoped>
.add-container {
  min-height: 100vh;
  padding: 32rpx;
  background: linear-gradient(180deg, #f4f8ff 0%, #eef4ff 100%);
  box-sizing: border-box;
}
.page-header {
  padding: 30rpx 24rpx;
  border-radius: 36rpx;
  background: rgba(59, 130, 246, 0.12);
  margin-bottom: 30rpx;
  box-sizing: border-box;
}
.page-title {
  font-size: 38rpx;
  font-weight: 800;
  color: #0f172a;
}
.page-note {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  color: #475569;
}
.form-card {
  padding: 30rpx;
  border-radius: 40rpx;
  background: #ffffff;
  box-shadow: 0 24rpx 50rpx rgba(15, 23, 42, 0.08);
  box-sizing: border-box;
  width: 100%;
}
.field {
  margin-bottom: 28rpx;
  width: 100%;
  box-sizing: border-box;
}
.field-row {
  display: flex;
  gap: 22rpx;
  width: 100%;
  box-sizing: border-box;
}
.small-field {
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
}
.label {
  font-size: 26rpx;
  color: #334155;
  margin-bottom: 16rpx;
  display: block;
}
.textarea,
.input {
  width: 100%;
  box-sizing: border-box;
  font-size: 28rpx;
  color: #0f172a;
  border: 1rpx solid rgba(148, 163, 184, 0.2);
  border-radius: 32rpx;
  background: #f8fafc;
}
.textarea {
  min-height: 170rpx;
  padding: 24rpx 22rpx;
  line-height: 44rpx;
}
.input {
  height: 104rpx;
  padding: 0 22rpx;
}
.material-section {
  margin-bottom: 28rpx;
  border-top: 1rpx solid rgba(148, 163, 184, 0.15);
  padding-top: 28rpx;
}
.material-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}
.material-toggle {
  font-size: 26rpx;
  color: #2563eb;
  font-weight: 600;
}
.material-body {
  border: 1rpx solid rgba(148, 163, 184, 0.15);
  border-radius: 24rpx;
  padding: 20rpx;
  background: #f8fafc;
}
.submit-btn {
  width: 100%;
  margin-top: 16rpx;
  padding: 18rpx 0;
  border-radius: 999rpx;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 700;
  box-sizing: border-box;
}
</style>
