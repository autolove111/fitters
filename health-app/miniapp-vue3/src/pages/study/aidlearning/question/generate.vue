<template>
  <view class="question-page">
    <text class="page-title">AI 题目生成</text>
    <u-input v-model="form.knowledge_point" placeholder="知识点" border="surround" />
    <u-input v-model="form.difficulty" placeholder="难度 (easy/medium/hard)" border="surround" />
    <u-input v-model="form.question_type" placeholder="题型 (choice/short_answer/essay)" border="surround" />
    <u-input v-model.number="count" placeholder="数量" type="number" border="surround" />
    <u-input v-model="kbName" placeholder="知识库名称 (可选)" border="surround" />
    <u-button type="primary" shape="circle" :loading="generating" @click="handleGenerate">生成题目</u-button>

    <view v-if="results.length > 0" class="results">
      <text class="section-title">生成结果</text>
      <view v-for="(q, i) in results" :key="i" class="question-card">
        <text class="q-index">{{ i + 1 }}.</text>
        <text class="q-text">{{ q.question || q.content || JSON.stringify(q) }}</text>
        <text v-if="q.answer" class="q-answer">答案: {{ q.answer }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { questionApi } from '../../api/question'

export default {
  data() {
    return {
      form: { knowledge_point: '', difficulty: 'medium', question_type: 'choice' },
      count: 5,
      kbName: '',
      generating: false,
      results: [],
    }
  },
  methods: {
    handleGenerate() {
      this.generating = true
      this.results = []
      questionApi.generate({
        requirement: this.form,
        kb_name: this.kbName || undefined,
        count: this.count,
      }, (msg) => {
        if (msg.type === 'result' || msg.type === 'content') {
          if (msg.questions) this.results = msg.questions
          else if (msg.content) {
            try { this.results = JSON.parse(msg.content) } catch (e) { this.results.push({ question: msg.content }) }
          }
        }
        if (msg.type === 'done' || msg.type === 'error') {
          this.generating = false
        }
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.question-page { padding: 30rpx; display: flex; flex-direction: column; gap: 24rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; }
.results { margin-top: 20rpx; }
.section-title { font-size: 30rpx; font-weight: 600; display: block; margin-bottom: 20rpx; }
.question-card {
  background: #fff; border-radius: 16rpx; padding: 24rpx; margin-bottom: 16rpx;
  .q-index { font-weight: 600; color: #4f46e5; margin-right: 8rpx; }
  .q-text { font-size: 28rpx; color: #1f2937; line-height: 1.6; }
  .q-answer { display: block; margin-top: 12rpx; font-size: 26rpx; color: #10b981; }
}
</style>
