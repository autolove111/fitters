<template>
  <view class="mimic-page">
    <text class="page-title">模拟试卷</text>
    <u-input v-model="kbName" placeholder="知识库名称" border="surround" />
    <u-input v-model.number="maxQuestions" placeholder="最大题目数" type="number" border="surround" />
    <view class="upload-area" @click="choosePdf">
      <u-icon name="file-text" size="60" color="#9ca3af" />
      <text>{{ pdfName || '选择 PDF 试卷' }}</text>
    </view>
    <u-button type="primary" shape="circle" :loading="generating" :disabled="!pdfName" @click="handleMimic">开始分析</u-button>

    <view v-if="results.length > 0" class="results">
      <text class="section-title">分析结果</text>
      <view v-for="(q, i) in results" :key="i" class="question-card">
        <text class="q-text">{{ q.question || q.content || JSON.stringify(q) }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { questionApi } from '../../api/question'

export default {
  data() {
    return { kbName: '', maxQuestions: 10, pdfName: '', pdfData: '', generating: false, results: [] }
  },
  methods: {
    choosePdf() {
      uni.chooseFile({
        count: 1,
        extension: ['.pdf'],
        success: (res) => {
          this.pdfName = res.tempFiles[0].name || '试卷.pdf'
          uni.getFileSystemManager().readFile({
            filePath: res.tempFiles[0].path,
            encoding: 'base64',
            success: (r) => { this.pdfData = r.data },
          })
        },
      })
    },
    handleMimic() {
      this.generating = true
      this.results = []
      questionApi.mimic({
        mode: 'upload',
        kb_name: this.kbName,
        pdf_data: this.pdfData,
        pdf_name: this.pdfName,
        max_questions: this.maxQuestions,
      }, (msg) => {
        if (msg.type === 'result' || msg.type === 'content') {
          if (msg.questions) this.results = msg.questions
          else if (msg.content) {
            try { this.results = JSON.parse(msg.content) } catch (e) { this.results.push({ question: msg.content }) }
          }
        }
        if (msg.type === 'done' || msg.type === 'error') this.generating = false
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.mimic-page { padding: 30rpx; display: flex; flex-direction: column; gap: 24rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; }
.upload-area {
  border: 2rpx dashed #d1d5db; border-radius: 16rpx; padding: 60rpx;
  display: flex; flex-direction: column; align-items: center; gap: 16rpx; color: #6b7280;
}
.results { margin-top: 20rpx; }
.section-title { font-size: 30rpx; font-weight: 600; display: block; margin-bottom: 20rpx; }
.question-card { background: #fff; border-radius: 16rpx; padding: 24rpx; margin-bottom: 16rpx; }
.q-text { font-size: 28rpx; color: #1f2937; line-height: 1.6; }
</style>
