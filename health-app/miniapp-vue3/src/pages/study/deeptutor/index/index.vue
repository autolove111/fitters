<template>
  <view class="workspace-page">
    <view class="shell">
      <view :class="['sidebar', { 'sidebar-open': isSidebarOpen }]">
        <view class="brand-block">
          <view class="brand-row">
            <view class="brand-mark">A</view>
            <text class="brand-name">AidLearning</text>
          </view>
          <!-- <view class="brand-badge">v1.4.0</view> -->
        </view>

        <view class="nav-section">
          <view class="primary-action" @click="startNewChat">
            <u-icon name="plus" size="30" color="#f3ece7" />
            <text>新建对话</text>
          </view>
        </view>

        <view class="nav-section">
          <text class="section-label">对话</text>
          <view class="session-group">
            <text class="group-label">{{ sessionGroupTitle }}</text>
            <view
              v-for="session in recentSessions"
              :key="session.id"
              class="session-link"
              @click="openSession(session.id)"
            >
              <view class="session-dot" />
              <text class="session-text">{{ session.title || '新对话' }}</text>
            </view>
            <text v-if="recentSessions.length === 0" class="session-empty">暂无对话记录</text>
          </view>
        </view>

        <view class="nav-section menu-stack">
          <view
            v-for="item in menuItems"
            :key="item.label"
            class="menu-item"
            @click="handleMenu(item)"
          >
            <u-icon :name="item.icon" size="30" color="#a59a92" />
            <text>{{ item.label }}</text>
          </view>
        </view>
      </view>

      <view class="page-topbar">
        <button class="menu-toggle-btn" @click="toggleSidebar">
          <u-icon name="menu" color="#0f172a" />
        </button>
      </view>

      <view class="main-panel">
        <view v-if="!messages.length" class="hero">
          <view class="hero-badge">
            <u-icon name="bookmark" size="34" color="#7d736d" />
          </view>
          <text class="hero-title">今天想学点什么？</text>
          <text class="hero-subtitle">制定计划、探索知识、开始你的专属学习对话</text>
        </view>

        <scroll-view
          v-else
          scroll-y
          class="messages-area"
          :scroll-into-view="scrollTarget"
          scroll-with-animation
        >
          <view v-for="(msg, index) in messages" :key="`${msg.role}-${index}`" :id="`msg-${index}`">
            <ChatMessage :message="msg" />
          </view>
          <view v-if="chatStore.state.isStreaming" class="streaming-row">
            <view class="streaming-bubble">
              <text>{{ chatStore.state.streamingContent || '思考中...' }}</text>
            </view>
          </view>
          <view id="msg-bottom" class="msg-bottom" />
        </scroll-view>

        <view class="composer-card">
          <view v-if="showCapabilityMenu" class="capability-menu">
            <view
              v-for="item in capabilityOptions"
              :key="item.key"
              class="capability-item"
              :class="{ active: selectedCapability.key === item.key }"
              @click="selectCapability(item)"
            >
              <view class="capability-copy">
                <view class="capability-title-row">
                  <u-icon :name="item.icon" size="26" :color="selectedCapability.key === item.key ? '#ea8f57' : '#b6ada5'" />
                  <text class="capability-title">{{ item.label }}</text>
                </view>
                <text class="capability-desc">{{ item.description }}</text>
              </view>
              <view v-if="selectedCapability.key === item.key" class="capability-dot" />
            </view>
          </view>

          <textarea
            v-model="draft"
            class="composer-textarea"
            maxlength="8000"
            placeholder="输入你的问题..."
            placeholder-class="composer-placeholder"
            @confirm="submitDraft"
          />

          <view class="composer-footer">
            <view class="composer-toolbar">
              <view class="tool-pill" @click="goKnowledge">
                <u-icon name="file-text" size="22" color="#a59a92" />
                <text>知识库</text>
              </view>
              <view class="tool-pill" @click="goSkills">
                <u-icon name="star" size="22" color="#a59a92" />
                <text>技能</text>
              </view>
              <view class="send-button" @click="submitDraft">
                <u-icon
                  :name="chatStore.state.isStreaming ? 'close-circle' : 'arrow-up'"
                  size="28"
                  :color="chatStore.state.isStreaming ? '#f6d6d1' : '#201d1a'"
                />
              </view>
            </view>
          </view>
        </view>
      </view>
      <view v-if="isSidebarOpen" class="sidebar-backdrop" @click="closeSidebar" />
    </view>
  </view>
</template>

<script>
import dayjs from 'dayjs'
import { useChatStore } from '../../store/chat'
import ChatMessage from '../../components/ChatMessage.vue'

const capabilityOptions = [
  {
    key: 'chat',
    value: 'chat',
    label: '对话',
    icon: 'chat',
    description: '灵活对话，支持多种工具',
  },
  {
    key: 'solve',
    value: 'deep_solve',
    label: '解题',
    icon: 'grid',
    description: '多步骤推理与问题求解',
  },
  {
    key: 'quiz',
    value: 'deep_question',
    label: '出题',
    icon: 'edit-pen',
    description: '自动生成练习题目',
  },
  {
    key: 'research',
    value: 'deep_research',
    label: '研究',
    icon: 'search',
    description: '多智能体深度研究',
  },
  {
    key: 'visualize',
    value: 'visualize',
    label: '可视化',
    icon: 'bar-chart',
    description: '生成图表与可视化解释',
  },
]

export default {
  components: { ChatMessage },
  data() {
    return {
      draft: '',
      chatStore: useChatStore(),
      recentSessions: [],
      scrollTarget: '',
      showCapabilityMenu: false,
      capabilityOptions,
      menuItems: [
        // { label: '会话', icon: 'clock', route: '/pages/study/deeptutor/chat/session' },
        { label: '知识库', icon: 'bookmark', route: '/pages/study/deeptutor/knowledge/list' },
        { label: '技能', icon: 'star', route: '/pages/study/deeptutor/skills/list' },
        // { label: '记忆', icon: 'heart', route: '/pages/study/deeptutor/memory/overview' },
        { label: '设置', icon: 'setting', route: '/pages/study/deeptutor/settings/index' },
      ],
      isSidebarOpen: false,
    }
  },
  computed: {
    messages() {
      return this.chatStore.state.messages
    },
    sessionGroupTitle() {
      if (!this.recentSessions.length) return '最近'
      const latest = this.recentSessions[0]?.updated_at
      if (!latest) return '最近'
      const latestKey = dayjs(latest).format('YYYY-MM-DD')
      if (latestKey === dayjs().format('YYYY-MM-DD')) return '今天'
      if (latestKey === dayjs().subtract(1, 'day').format('YYYY-MM-DD')) return '昨天'
      return dayjs(latest).format('MM月DD日')
    },
    selectedCapability() {
      return this.capabilityOptions.find((item) => item.value === this.chatStore.state.capability) || this.capabilityOptions[0]
    },
    selectedModelLabel() {
      return this.chatStore.state.selectedModel || 'Select model'
    },
  },
  watch: {
    messages: {
      deep: true,
      handler() {
        this.scrollToBottom()
      },
    },
    'chatStore.state.streamingContent'() {
      this.scrollToBottom()
    },
    'chatStore.state.isStreaming'(value) {
      if (!value) {
        this.loadRecent()
      }
    },
  },
  onShow() {
    this.chatStore.ensureConnected()
    if (!this.chatStore.state.capability || this.chatStore.state.capability === 'tutor') {
      this.chatStore.state.capability = 'chat'
    }
    this.loadRecent()
    this.scrollToBottom()
  },
  methods: {
    async loadRecent() {
      try {
        const sessions = await this.chatStore.loadSessions(8, 0)
        this.recentSessions = sessions.slice(0, 5)
      } catch (e) {
        this.recentSessions = []
      }
    },
    handleMenu(item) {
      uni.navigateTo({ url: item.route })
      this.isSidebarOpen = false
    },
    startNewChat() {
      this.chatStore.newSession()
      this.draft = ''
      this.showCapabilityMenu = false
      this.isSidebarOpen = false
    },
    async openSession(id) {
      try {
        await this.chatStore.loadSession(id)
        this.showCapabilityMenu = false
        this.isSidebarOpen = false
        this.scrollToBottom()
      } catch (e) {
        uni.showToast({ title: '打开对话失败', icon: 'none' })
      }
    },
    toggleCapabilityMenu() {
      this.showCapabilityMenu = !this.showCapabilityMenu
    },
    selectCapability(item) {
      this.chatStore.state.capability = item.value
      this.showCapabilityMenu = false
    },
    submitDraft() {
      if (this.chatStore.state.isStreaming) {
        this.chatStore.cancelStreaming()
        return
      }
      const text = (this.draft || '').trim()
      if (!text) return
      if (this.chatStore.state.messages.length === 0 && this.chatStore.state.currentSessionId) {
        this.chatStore.newSession()
      }
      this.chatStore.sendMessage(text)
      this.draft = ''
      this.showCapabilityMenu = false
      this.scrollToBottom()
      this.loadRecent()
    },
    goKnowledge() {
      this.showCapabilityMenu = false
      uni.navigateTo({ url: '/pages/study/deeptutor/knowledge/list' })
    },
    goSkills() {
      this.showCapabilityMenu = false
      uni.navigateTo({ url: '/pages/study/deeptutor/skills/list' })
    },
    goMemory() {
      this.showCapabilityMenu = false
      uni.navigateTo({ url: '/pages/study/deeptutor/memory/overview' })
      this.isSidebarOpen = false
    },
    toggleSidebar() {
      this.isSidebarOpen = !this.isSidebarOpen
    },
    closeSidebar() {
      this.isSidebarOpen = false
    },
    scrollToBottom() {
      setTimeout(() => {
        this.scrollTarget = ''
        this.$nextTick(() => {
          this.scrollTarget = 'msg-bottom'
        })
      }, 50)
    },
  },
}
</script>

<style lang="scss" scoped>
.workspace-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f3f9ff 0%, #eef5ff 100%);
  color: #0f172a;
}

.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 300rpx;
  background: linear-gradient(180deg, rgba(243, 249, 255, 0.98), rgba(238, 245, 255, 0.98));
  backdrop-filter: blur(20rpx);
  border-right: 1rpx solid rgba(255, 255, 255, 0.7);
  padding: 28rpx 24rpx 32rpx;
  transform: translateX(-100%);
  transition: transform 0.3s ease;
  z-index: 900;
  overflow-y: auto;
}

.sidebar-open {
  transform: translateX(0);
}

.sidebar-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  z-index: 850;
}

.brand-block {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28rpx;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.brand-mark {
  width: 56rpx;
  height: 56rpx;
  border-radius: 18rpx;
  background: linear-gradient(135deg, #0ea5e9, #14b8a6);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 30rpx;
}

.brand-name {
  font-size: 40rpx;
  font-weight: 600;
  color: #0f172a;
  font-family: Georgia, 'Times New Roman', serif;
}

.brand-badge {
  font-size: 22rpx;
  color: #64748b;
}

.nav-section {
  margin-bottom: 28rpx;
}

.primary-action {
  height: 72rpx;
  border-radius: 999rpx;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  color: #ffffff;
  border: none;
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 0 24rpx;
  font-size: 26rpx;
  font-weight: 700;
  box-shadow: 0 16rpx 24rpx rgba(56, 189, 248, 0.22);
}

.section-label {
  display: block;
  font-size: 28rpx;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 16rpx;
}

.session-group {
  padding: 6rpx 0;
}

.group-label {
  display: block;
  margin-bottom: 14rpx;
  font-size: 20rpx;
  letter-spacing: 2rpx;
  color: #64748b;
}

.session-link {
  display: flex;
  align-items: center;
  gap: 14rpx;
  padding: 14rpx 8rpx;
}

.session-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: #38bdf8;
}

.session-text,
.session-empty,
.menu-item text,
.tool-pill text,
.model-pill text,
.capability-pill text {
  white-space: nowrap;
}

.session-text {
  max-width: 320rpx;
  font-size: 26rpx;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-empty {
  font-size: 24rpx;
  color: #64748b;
}

.menu-stack {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.menu-item {
  height: 76rpx;
  border-radius: 26rpx;
  padding: 0 20rpx;
  display: flex;
  align-items: center;
  gap: 12rpx;
  background: rgba(59, 130, 246, 0.12);
  color: #0f172a;
  font-size: 26rpx;
  font-weight: 600;
}

.main-panel {
  flex: 1;
  padding: 120rpx 24rpx 40rpx;
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: relative;
  z-index: 1;
  isolation: isolate;
}

.page-topbar {
  position: fixed;
  top: 24rpx;
  right: 24rpx;
  z-index: 1000;
}

.menu-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  height: 64rpx;
  padding: 0 20rpx;
  border-radius: 999rpx;
  background: rgba(59, 130, 246, 0.12);
  border: 1rpx solid rgba(255, 255, 255, 0.7);
  color: #0f172a;
  font-size: 24rpx;
}

.hero {
  flex: 1;
  min-height: 420rpx;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 80rpx 24rpx 50rpx;
}

.hero-badge {
  width: 88rpx;
  height: 88rpx;
  border-radius: 28rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.7);
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(96, 165, 250, 0.18));
  backdrop-filter: blur(20rpx);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 22rpx 50rpx rgba(59, 130, 246, 0.12);
}

.hero-title {
  margin-top: 28rpx;
  font-size: 72rpx;
  line-height: 1.08;
  font-family: Georgia, 'Times New Roman', serif;
  color: #0f172a;
}

.hero-subtitle {
  margin-top: 18rpx;
  max-width: 760rpx;
  font-size: 28rpx;
  line-height: 1.7;
  color: #475569;
}

.messages-area {
  flex: 1;
  min-height: 0;
  margin-bottom: 20rpx;
  padding: 16rpx 6rpx 0;
}

.streaming-row {
  display: flex;
  margin-bottom: 24rpx;
}

.streaming-bubble {
  max-width: 85%;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(229, 242, 255, 0.98));
  backdrop-filter: blur(20rpx);
  padding: 24rpx 30rpx;
  border-radius: 28rpx 28rpx 28rpx 4rpx;
  font-size: 28rpx;
  color: #0f172a;
  line-height: 1.6;
  border: 1rpx solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 8rpx 20rpx rgba(15, 23, 42, 0.06);
}

.msg-bottom {
  height: 20rpx;
}

.composer-card {
  width: 100%;
  max-width: 1100rpx;
  align-self: center;
  border-radius: 40rpx;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(229, 242, 255, 0.98));
  backdrop-filter: blur(20rpx);
  border: 1rpx solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 28rpx 50rpx rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.capability-menu {
  margin: 22rpx 22rpx 0;
  border-radius: 36rpx;
  overflow: hidden;
  border: 1rpx solid rgba(255, 255, 255, 0.85);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(229, 242, 255, 0.98));
  backdrop-filter: blur(20rpx);
  box-shadow: 0 20rpx 44rpx rgba(14, 165, 233, 0.14);
}

.capability-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  padding: 24rpx 28rpx;
  border-bottom: 1rpx solid rgba(148, 163, 184, 0.12);
}

.capability-item:last-child {
  border-bottom: none;
}

.capability-item.active {
  background: rgba(59, 130, 246, 0.14);
}

.capability-copy {
  min-width: 0;
}

.capability-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.capability-title {
  font-size: 34rpx;
  color: #0f172a;
  font-weight: 600;
}

.capability-desc {
  display: block;
  margin-top: 8rpx;
  font-size: 25rpx;
  color: #475569;
  line-height: 1.4;
}

.capability-dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: linear-gradient(90deg, #0ea5e9, #14b8a6);
  flex-shrink: 0;
}

.composer-textarea {
  width: 100%;
  height: 180rpx;
  max-height: 320rpx;
  padding: 34rpx 34rpx 22rpx;
  color: #0f172a;
  font-size: 32rpx;
  line-height: 1.65;
  background: transparent;
  box-sizing: border-box;
  overflow-y: auto;
}

.composer-placeholder {
  color: #94a3b8;
}

.composer-footer {
  border-top: 1rpx solid rgba(148, 163, 184, 0.16);
  padding: 18rpx 20rpx 18rpx 24rpx;
}

.composer-toolbar {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.capability-pill,
.tool-pill {
  display: flex;
  align-items: center;
  gap: 10rpx;
  height: 64rpx;
  padding: 0 20rpx;
  border-radius: 26rpx;
  background: rgba(59, 130, 246, 0.12);
  color: #0f172a;
  font-size: 24rpx;
  font-weight: 600;
  border: 1rpx solid rgba(255, 255, 255, 0.7);
}

.capability-pill.active {
  background: rgba(59, 130, 246, 0.18);
  border-color: rgba(255, 255, 255, 0.85);
  color: #0f172a;
  box-shadow: 0 8rpx 20rpx rgba(59, 130, 246, 0.12);
}


.send-button {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: auto;
}

@media screen and (min-width: 960px) {
  .shell {
    flex-direction: row;
  }

  .sidebar {
    width: 300rpx;
    min-width: 300rpx;
    min-height: 100vh;
    border-bottom: none;
    border-right: 1rpx solid rgba(255, 255, 255, 0.7);
    transform: translateX(0);
  }

  .page-topbar {
    display: none;
  }

  .main-panel {
    padding-top: 40rpx;
    margin-left: 300rpx;
    width: calc(100% - 300rpx);
  }

  .menu-item {
    width: 100%;
    margin-bottom: 10rpx;
    background: transparent;
  }
}

@media screen and (max-width: 959px) {
  .hero-title {
    font-size: 54rpx;
    color: #0f172a;
  }

  .composer-textarea {
    height: 160rpx;
    font-size: 28rpx;
  }

}
</style>
