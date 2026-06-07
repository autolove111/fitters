<template>
  <view class="md-renderer">
    <rich-text :nodes="parsed" />
  </view>
</template>

<script>
export default {
  props: {
    content: { type: String, default: '' },
  },
  computed: {
    parsed() {
      return this.parseMarkdown(this.content)
    },
  },
  methods: {
    parseMarkdown(md) {
      if (!md) return ''
      let html = md
      // Code blocks
      html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>')
      // Inline code
      html = html.replace(/`([^`]+)`/g, '<code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;font-size:13px;">$1</code>')
      // Headers
      html = html.replace(/^### (.+)$/gm, '<h3 style="font-size:16px;font-weight:600;margin:12px 0 6px;">$1</h3>')
      html = html.replace(/^## (.+)$/gm, '<h2 style="font-size:18px;font-weight:700;margin:14px 0 8px;">$1</h2>')
      html = html.replace(/^# (.+)$/gm, '<h1 style="font-size:20px;font-weight:700;margin:16px 0 10px;">$1</h1>')
      // Bold & italic
      html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Links
      html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color:#4f46e5;">$1</a>')
      // Lists
      html = html.replace(/^- (.+)$/gm, '<div style="padding-left:16px;">&bull; $1</div>')
      html = html.replace(/^\d+\. (.+)$/gm, '<div style="padding-left:16px;">$1</div>')
      // Paragraphs
      html = html.replace(/\n\n/g, '</p><p style="margin:8px 0;line-height:1.6;">')
      html = html.replace(/\n/g, '<br/>')
      html = '<p style="margin:0;line-height:1.6;">' + html + '</p>'
      // Clean up empty tags
      html = html.replace(/<p[^>]*><\/p>/g, '')
      return html
    },
  },
}
</script>

<style lang="scss" scoped>
.md-renderer { font-size: 28rpx; color: #1f2937; line-height: 1.6; }
</style>
