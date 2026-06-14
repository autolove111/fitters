<template>
  <view class="add-container" :class="{ dark: isDark }">
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

      <!-- 时间段选择 -->
      <view class="field-row">
        <view class="field small-field">
          <text class="label">开始日期</text>
          <picker mode="date" :value="startDate" @change="onStartDateChange">
            <view class="picker-btn">
              <text class="picker-icon">📅</text>
              <text class="picker-text" :class="{ placeholder: !startDate }">
                {{ formatDisplayDate(startDate) || '选择日期' }}
              </text>
            </view>
          </picker>
        </view>
        <view class="field small-field">
          <text class="label">结束日期</text>
          <picker mode="date" :value="endDate" :start="startDate" @change="onEndDateChange">
            <view class="picker-btn">
              <text class="picker-icon">📅</text>
              <text class="picker-text" :class="{ placeholder: !endDate }">
                {{ formatDisplayDate(endDate) || '选择日期' }}
              </text>
            </view>
          </picker>
        </view>
      </view>

      <!-- 上传文件到知识库区域 -->
      <view class="kb-upload-section">
        <text class="label">上传学习资料到知识库（可选）</text>
        <text class="kb-upload-desc">选择文件后会自动创建以计划内容命名的知识库</text>

        <view class="kb-upload-btn" @click="chooseFilesForKB">
          <text class="kb-upload-icon">📚</text>
          <text class="kb-upload-text">选择文件</text>
        </view>

        <view v-if="kbFiles.length > 0" class="kb-file-list">
          <view v-for="(f, i) in kbFiles" :key="i" class="kb-file-item">
            <text class="kb-file-name">{{ f.name }}</text>
            <text class="kb-file-remove" @click="removeKBFile(i)">✕</text>
          </view>
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
import { studyApi, knowledgeApi } from '@/utils/api'
import { useThemeStore } from '@/store/theme'
const themeStore = useThemeStore()
const { isDark } = themeStore

const content = ref('')
const startDate = ref('')
const endDate = ref('')
const kbFiles = ref([])
const submitting = ref(false)
const submitText = ref('提交中...')

// 获取今天的日期作为默认值
const today = new Date()
const year = today.getFullYear()
const month = String(today.getMonth() + 1).padStart(2, '0')
const day = String(today.getDate()).padStart(2, '0')
const todayStr = `${year}-${month}-${day}`
startDate.value = todayStr
endDate.value = todayStr

// 格式化显示日期：2026-06-07 -> 6月7日
function formatDisplayDate(dateStr) {
  if (!dateStr) return ''
  const parts = dateStr.split('-')
  if (parts.length !== 3) return dateStr
  const m = parseInt(parts[1], 10)
  const d = parseInt(parts[2], 10)
  return `${m}月${d}日`
}

// 开始日期选择
function onStartDateChange(e) {
  startDate.value = e.detail.value
  // 如果结束日期早于开始日期，自动调整
  if (endDate.value && endDate.value < startDate.value) {
    endDate.value = startDate.value
  }
}

// 结束日期选择
function onEndDateChange(e) {
  endDate.value = e.detail.value
}

// 选择文件上传到知识库
function chooseFilesForKB() {
  uni.chooseFile({
    count: 9,
    type: 'file',
    success: (res) => {
      res.tempFiles.forEach((f) => {
        kbFiles.value.push({
          path: f.path,
          name: f.name || f.path.split('/').pop()
        })
      })
    }
  })
}

// 移除已选文件
function removeKBFile(index) {
  kbFiles.value.splice(index, 1)
}

async function submitPlan() {
  if (!content.value.trim()) {
    uni.showToast({ title: '请填写计划内容', icon: 'none' })
    return
  }
  if (!startDate.value || !endDate.value) {
    uni.showToast({ title: '请选择开始和结束日期', icon: 'none' })
    return
  }

  submitting.value = true
  try {
    // 1. 保存学习计划
    submitText.value = '保存计划中...'
    const startDisplay = formatDisplayDate(startDate.value)
    const endDisplay = formatDisplayDate(endDate.value)
    await studyApi.add({
      content: content.value,
      start: `${startDate.value} 00:00`,
      end: `${endDate.value} 23:59`
    })

    // 2. 如果有文件，上传到知识库
    if (kbFiles.value.length > 0) {
      const kbName = '计划-' + content.value.trim().substring(0, 20)
      submitText.value = `创建知识库「${kbName}」...`

      try {
        // 用第一个文件创建知识库
        await knowledgeApi.create(kbName, kbFiles.value[0].path)

        // 剩余文件追加上传
        for (let i = 1; i < kbFiles.value.length; i++) {
          submitText.value = `上传第 ${i + 1}/${kbFiles.value.length} 个文件...`
          await knowledgeApi.upload(kbName, kbFiles.value[i].path)
        }

        uni.showToast({ title: '计划已保存，资料已上传到知识库', icon: 'success', duration: 2000 })
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
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
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
  color: var(--text-primary);
}
.page-note {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  color: var(--text-secondary);
}
.form-card {
  padding: 30rpx;
  border-radius: 40rpx;
  background: var(--card-bg);
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
  color: var(--text-primary);
  margin-bottom: 16rpx;
  display: block;
}

.picker-btn {
  display: flex;
  align-items: center;
  gap: 12rpx;
  height: 104rpx;
  padding: 0 24rpx;
  border: 1rpx solid var(--input-border);
  border-radius: 32rpx;
  background: var(--input-bg);
}

.picker-icon {
  font-size: 32rpx;
}

.picker-text {
  font-size: 28rpx;
  color: var(--text-primary);
}

.picker-text.placeholder {
  color: #94a3b8;
}
.textarea,
.input {
  width: 100%;
  box-sizing: border-box;
  font-size: 28rpx;
  color: var(--text-primary);
  border: 1rpx solid var(--input-border);
  border-radius: 32rpx;
  background: var(--input-bg);
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

/* 知识库上传区域 */
.kb-upload-section {
  margin-bottom: 28rpx;
  border-top: 1rpx solid rgba(148, 163, 184, 0.15);
  padding-top: 28rpx;
}

.kb-upload-desc {
  display: block;
  font-size: 24rpx;
  color: #94a3b8;
  margin-bottom: 16rpx;
}

.kb-upload-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  height: 80rpx;
  border-radius: 24rpx;
  border: 2rpx dashed rgba(139, 92, 246, 0.3);
  background: rgba(139, 92, 246, 0.05);
  margin-bottom: 16rpx;
}

.kb-upload-icon {
  font-size: 32rpx;
}

.kb-upload-text {
  font-size: 28rpx;
  color: #7c3aed;
  font-weight: 600;
}

.kb-file-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.kb-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx 20rpx;
  background: rgba(139, 92, 246, 0.08);
  border-radius: 16rpx;
}

.kb-file-name {
  font-size: 26rpx;
  color: #1a1a1a;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 16rpx;
}

.kb-file-remove {
  font-size: 28rpx;
  color: #94a3b8;
  padding: 8rpx;
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
