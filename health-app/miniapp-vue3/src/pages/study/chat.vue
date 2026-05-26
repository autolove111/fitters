<template>
  <view class="chat-container">
    <view class="chat-header">
      <text class="title">{{ planTitle || '个人知识助手' }}</text>
    </view>

    <scroll-view class="messages" :scroll-y="true" :scroll-with-animation="true">
      <view v-for="(m, idx) in messages" :key="idx" :class="['message', m.role]">
        <text>{{ m.text }}</text>
      </view>
    </scroll-view>

    <view class="composer">
      <input class="input" v-model="inputText" placeholder="向助手提问..." placeholder-class="placeholder"/>
      <button class="send" @click="send">发送</button>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { assistantApi } from '@/utils/api'

const inputText = ref('')
const messages = ref([])
const planId = ref(null)
const planTitle = ref('')

onMounted(() => {
  const pages = getCurrentPages ? getCurrentPages() : []
  // 通过 options 读取参数
  const option = __uniConfig && __uniConfig.pageData ? __uniConfig.pageData : null
  // 更可靠地使用页面路由参数
  const query = (typeof getCurrentPages === 'function' && getCurrentPages().slice(-1)[0]?.options) || {}
  planId.value = query.planId || query.planid || null
  planTitle.value = decodeURIComponent(query.title || '')
  messages.value.push({ role: 'system', text: `学习计划：${planTitle.value || '未命名'}` })
})

async function send() {
  if (!inputText.value.trim()) return
  const text = inputText.value
  messages.value.push({ role: 'user', text })
  inputText.value = ''

  try {
    const payload = { planId: planId.value, input: text }
    const reply = await assistantApi.chat(payload)
    // 假设后端返回字符串或 { text }
    const replyText = (reply && (reply.text || reply)) || '（助手未返回内容）'
    messages.value.push({ role: 'assistant', text: replyText })
  } catch (e) {
    messages.value.push({ role: 'assistant', text: '请求失败：' + (e.message || e) })
  }
}
</script>

<style scoped>
.chat-container { display:flex; flex-direction:column; height:100vh; }
.chat-header { padding: 36rpx 24rpx; background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%); border-bottom: 1rpx solid #1d4ed8; display:flex; flex-direction:column; align-items:center; justify-content:center; box-shadow: 0 2rpx 8rpx rgba(59,130,246,0.18); }
.chat-header .title { font-size: 40rpx; font-weight:800; color: #ffffff; letter-spacing: 1rpx; }
.messages { flex:1; padding: 20rpx; background: #f7fbff; }
.message { padding: 16rpx; border-radius: 18rpx; margin-bottom: 12rpx; max-width: 80%; }
.message.user { background: #dbeafe; align-self: flex-end; }
.message.assistant { background: #ffffff; align-self: flex-start; }
.message.system { background: transparent; color: #374151; font-weight:600; }
.composer { display:flex; gap:12rpx; padding: 16rpx; background: #fff; border-top:1rpx solid #eee }
.input { flex:1; height: 68rpx; padding: 14rpx; border-radius: 34rpx; background: #f1f5f9 }
.send { background: #06b6d4; color:#fff; padding: 14rpx 20rpx; border-radius: 34rpx }
</style>
