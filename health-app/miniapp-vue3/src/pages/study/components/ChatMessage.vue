<template>
  <view :class="['chat-msg', message.role]">
    <view v-if="message.role === 'user'" class="user-bubble">
      <text>{{ message.content }}</text>
    </view>
    <view v-else class="assistant-bubble">
      <view v-if="message.thinking" class="thinking-block" @click="showThinking = !showThinking">
        <text class="thinking-label">思考过程</text>
        <view v-if="showThinking" class="thinking-content">
          <text>{{ message.thinking }}</text>
        </view>
      </view>
      <view class="content">
        <rich-text :nodes="renderedContent" />
      </view>
      <view v-if="message.tool_calls && message.tool_calls.length" class="tool-calls">
        <view v-for="(tc, i) in message.tool_calls" :key="i" class="tool-call">
          <u-icon name="setting" size="24" color="#6b7280" />
          <text>{{ tc.name || tc.function?.name || 'tool' }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { marked } from 'marked'
import katex from 'katex'

marked.setOptions({ breaks: true, gfm: true })

// ============ KaTeX 渲染（HTML 输出 + 内联样式） ============

function latexToHtml(tex, displayMode) {
  try {
    const html = katex.renderToString(tex, {
      displayMode: !!displayMode,
      throwOnError: false,
      output: 'html',
      trust: true,
    })
    // 给 katex 容器加内联样式，确保 rich-text 中可读
    return html
      .replace(/class="katex"/g, 'style="font-size:1.1em;line-height:1.4;color:#1f2937;" class="katex"')
      .replace(/class="katex-display"/g, 'style="margin:12rpx 0;padding:16rpx 20rpx;background:#f8fafc;border-radius:12rpx;overflow-x:auto;text-align:center;" class="katex-display"')
      // 去掉依赖 CSS 定位的 vlist-strut（这些在 rich-text 中无效，去掉后文字会线性排列但不会重叠）
      .replace(/<span class="pstrut"[^>]*><\/span>/g, '')
      .replace(/<span class="strut"[^>]*><\/span>/g, '')
      // 给上标/下标容器加 font-size 使其与正文区分
      .replace(/class="sizing reset-size6 size3"/g, 'style="font-size:0.7em;"')
      .replace(/class="sizing reset-size6 size4"/g, 'style="font-size:0.8em;"')
      .replace(/class="sizing reset-size6 size5"/g, 'style="font-size:0.9em;"')
      .replace(/class="sizing reset-size6 size6"/g, 'style="font-size:1em;"')
      .replace(/class="sizing reset-size6 size7"/g, 'style="font-size:1.2em;"')
      .replace(/class="sizing reset-size6 size8"/g, 'style="font-size:1.4em;"')
      .replace(/class="sizing reset-size6 size9"/g, 'style="font-size:1.6em;"')
      .replace(/class="sizing reset-size6 size10"/g, 'style="font-size:1.8em;"')
      .replace(/class="sizing reset-size6 size11"/g, 'style="font-size:2em;"')
  } catch {
    return displayMode
      ? '<p style="color:#ef4444;font-size:24rpx;">[LaTeX 渲染失败]</p>'
      : '<span style="color:#ef4444;font-size:24rpx;">[LaTeX 渲染失败]</span>'
  }
}

// ============ LaTeX 占位符处理 ============

function processMath(text) {
  const blocks = []
  const inlines = []

  // $$...$$ 块级公式
  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, tex) => {
    const idx = blocks.length
    blocks.push(latexToHtml(tex.trim(), true))
    return `%%MATH_BLOCK_${idx}%%`
  })

  // $...$ 行内公式（跳过 \$）
  result = result.replace(/(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g, (_, tex) => {
    const idx = inlines.length
    inlines.push(latexToHtml(tex.trim(), false))
    return `%%MATH_INLINE_${idx}%%`
  })

  return { text: result, blocks, inlines }
}

function restoreMath(html, blocks, inlines) {
  blocks.forEach((h, i) => { html = html.replace(`%%MATH_BLOCK_${i}%%`, h) })
  inlines.forEach((h, i) => { html = html.replace(`%%MATH_INLINE_${i}%%`, h) })
  return html
}

// ============ Markdown HTML 内联样式 ============

const styleMap = {
  h1: 'font-size:36rpx;font-weight:700;color:#0f172a;margin:20rpx 0 12rpx;',
  h2: 'font-size:32rpx;font-weight:700;color:#0f172a;margin:18rpx 0 10rpx;',
  h3: 'font-size:30rpx;font-weight:600;color:#0f172a;margin:16rpx 0 8rpx;',
  h4: 'font-size:28rpx;font-weight:600;color:#0f172a;margin:14rpx 0 6rpx;',
  p: 'margin:8rpx 0;line-height:1.7;color:#1f2937;',
  pre: 'background:#f1f5f9;border-radius:12rpx;padding:20rpx;margin:12rpx 0;overflow-x:auto;',
  code: 'font-family:Menlo,Consolas,monospace;font-size:24rpx;',
  'inline-code': 'background:#f1f5f9;border-radius:6rpx;padding:2rpx 8rpx;font-family:Menlo,Consolas,monospace;font-size:24rpx;color:#e11d48;',
  blockquote: 'border-left:6rpx solid #cbd5e1;padding-left:20rpx;margin:12rpx 0;color:#64748b;',
  ul: 'padding-left:32rpx;margin:8rpx 0;',
  ol: 'padding-left:32rpx;margin:8rpx 0;',
  li: 'margin:4rpx 0;line-height:1.6;color:#1f2937;',
  table: 'border-collapse:collapse;margin:12rpx 0;width:100%;',
  th: 'border:1rpx solid #e2e8f0;padding:10rpx 14rpx;background:#f8fafc;font-weight:600;text-align:left;color:#0f172a;',
  td: 'border:1rpx solid #e2e8f0;padding:10rpx 14rpx;color:#1f2937;',
  hr: 'border:none;border-top:1rpx solid #e2e8f0;margin:16rpx 0;',
  a: 'color:#2563eb;text-decoration:underline;',
  strong: 'font-weight:700;color:#0f172a;',
  em: 'font-style:italic;',
  img: 'max-width:100%;border-radius:8rpx;margin:8rpx 0;',
}

function styleHtml(html) {
  return html
    .replace(/<h1>/g, `<h1 style="${styleMap.h1}">`)
    .replace(/<h2>/g, `<h2 style="${styleMap.h2}">`)
    .replace(/<h3>/g, `<h3 style="${styleMap.h3}">`)
    .replace(/<h4>/g, `<h4 style="${styleMap.h4}">`)
    .replace(/<p>/g, `<p style="${styleMap.p}">`)
    .replace(/<pre>/g, `<pre style="${styleMap.pre}">`)
    .replace(/<code>/g, `<code style="${styleMap.code}">`)
    .replace(/<blockquote>/g, `<blockquote style="${styleMap.blockquote}">`)
    .replace(/<ul>/g, `<ul style="${styleMap.ul}">`)
    .replace(/<ol>/g, `<ol style="${styleMap.ol}">`)
    .replace(/<li>/g, `<li style="${styleMap.li}">`)
    .replace(/<table>/g, `<table style="${styleMap.table}">`)
    .replace(/<th>/g, `<th style="${styleMap.th}">`)
    .replace(/<td>/g, `<td style="${styleMap.td}">`)
    .replace(/<hr\s*\/?>/g, `<hr style="${styleMap.hr}"/>`)
    .replace(/<a\s/g, `<a style="${styleMap.a}" `)
    .replace(/<strong>/g, `<strong style="${styleMap.strong}">`)
    .replace(/<em>/g, `<em style="${styleMap.em}">`)
    .replace(/<img\s/g, `<img style="${styleMap.img}" `)
    .replace(/<code style="[^"]*">/g, (match, offset) => {
      const before = html.substring(0, offset)
      if (before.lastIndexOf('<pre') > before.lastIndexOf('</pre>')) return match
      return `<code style="${styleMap['inline-code']}">`
    })
}

export default {
  props: {
    message: { type: Object, required: true },
  },
  data() {
    return { showThinking: false }
  },
  computed: {
    renderedContent() {
      if (this.message.role === 'user') return this.message.content
      const raw = this.message.content || ''
      if (!raw) return ''
      try {
        const { text, blocks, inlines } = processMath(raw)
        const mdHtml = marked.parse(text)
        const styled = styleHtml(mdHtml)
        return restoreMath(styled, blocks, inlines)
      } catch {
        return raw
      }
    },
  },
}
</script>

<style lang="scss" scoped>
.chat-msg { margin-bottom: 24rpx; display: flex; }
.chat-msg.user { justify-content: flex-end; }
.chat-msg.assistant { justify-content: flex-start; }

.user-bubble {
  max-width: 80%; background: #4f46e5; color: #fff; padding: 24rpx 30rpx;
  border-radius: 20rpx 20rpx 4rpx 20rpx; font-size: 28rpx; line-height: 1.6;
}
.assistant-bubble {
  max-width: 85%; background: #fff; padding: 24rpx 30rpx;
  border-radius: 20rpx 20rpx 20rpx 4rpx; font-size: 28rpx; color: #1f2937; line-height: 1.6;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04);
}
.content {
  word-break: break-all;
  overflow-x: auto;
}
.thinking-block {
  background: #f9fafb; border-radius: 12rpx; padding: 16rpx; margin-bottom: 16rpx;
  border-left: 4rpx solid #a5b4fc;
}
.thinking-label { font-size: 24rpx; color: #6366f1; font-weight: 500; display: block; margin-bottom: 8rpx; }
.thinking-content { font-size: 24rpx; color: #6b7280; line-height: 1.5; }
.tool-calls { margin-top: 16rpx; display: flex; flex-wrap: wrap; gap: 8rpx; }
.tool-call {
  display: flex; align-items: center; gap: 6rpx;
  background: #f3f4f6; padding: 6rpx 16rpx; border-radius: 8rpx;
  font-size: 22rpx; color: #6b7280;
}
</style>
