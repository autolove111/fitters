<template>
  <view class="workspace-page">
    <view class="shell">
      <view class="sidebar">
        <view class="brand-block">
          <view class="brand-row">
            <view class="brand-mark">A</view>
            <text class="brand-name">AidLearning</text>
          </view>
          <view class="brand-badge">v1.4.0</view>
        </view>

        <view class="nav-section">
          <view class="primary-action" @click="startNewChat">
            <u-icon name="plus" size="30" color="#f3ece7" />
            <text>New Chat</text>
          </view>
        </view>

        <view class="nav-section">
          <text class="section-label">Chat</text>
          <view class="session-group">
            <text class="group-label">{{ sessionGroupTitle }}</text>
            <view
              v-for="session in recentSessions"
              :key="session.id"
              class="session-link"
              @click="openSession(session.id)"
            >
              <view class="session-dot" />
              <text class="session-text">{{ session.title || 'New chat' }}</text>
            </view>
            <text v-if="recentSessions.length === 0" class="session-empty">No chat history yet</text>
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

      <view class="main-panel">
        <view v-if="!messages.length" class="hero">
          <view class="hero-badge">
            <u-icon name="bookmark" size="34" color="#7d736d" />
          </view>
          <text class="hero-title">What would you like to learn?</text>
          <text class="hero-subtitle">Plan, explore, and start a new tutoring conversation from one place.</text>
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
              <text>{{ chatStore.state.streamingContent || 'Thinking...' }}</text>
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
            auto-height
            maxlength="8000"
            placeholder="How can I help you today?"
            placeholder-class="composer-placeholder"
            @confirm="submitDraft"
          />

          <view class="composer-footer">
            <view class="composer-toolbar">
              <view class="left-actions">
                <view class="capability-pill active" @click="toggleCapabilityMenu">
                  <u-icon :name="selectedCapability.icon" size="22" color="#ea8f57" />
                  <text>{{ selectedCapability.label }}</text>
                  <u-icon :name="showCapabilityMenu ? 'arrow-up' : 'arrow-down'" size="18" color="#ea8f57" />
                </view>
                <view class="tool-pill" @click="goKnowledge">
                  <u-icon name="file-text" size="22" color="#a59a92" />
                  <text>Knowledge</text>
                </view>
                <view class="tool-pill" @click="goSkills">
                  <u-icon name="star" size="22" color="#a59a92" />
                  <text>Skill</text>
                </view>
                <view class="tool-pill" @click="goMemory">
                  <u-icon name="bookmark" size="22" color="#a59a92" />
                  <text>Memory</text>
                </view>
              </view>

              <view class="composer-actions">
                <view class="model-pill">
                  <u-icon name="grid" size="22" color="#8f8178" />
                  <text>{{ selectedModelLabel }}</text>
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
      </view>
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
    label: 'Chat',
    icon: 'chat',
    description: 'Flexible conversation with any tool',
  },
  {
    key: 'solve',
    value: 'deep_solve',
    label: 'Solve',
    icon: 'grid',
    description: 'Multi-step reasoning & problem solving',
  },
  {
    key: 'quiz',
    value: 'deep_question',
    label: 'Quiz',
    icon: 'edit-pen',
    description: 'Auto-validated question generation',
  },
  {
    key: 'research',
    value: 'deep_research',
    label: 'Research',
    icon: 'search',
    description: 'Comprehensive multi-agent research',
  },
  {
    key: 'visualize',
    value: 'visualize',
    label: 'Visualize',
    icon: 'bar-chart',
    description: 'Generate charts, diagrams, and visual explanations',
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
        { label: 'Sessions', icon: 'clock', route: '/pages/study/deeptutor/chat/session' },
        { label: 'Knowledge', icon: 'bookmark', route: '/pages/study/deeptutor/knowledge/list' },
        { label: 'Skills', icon: 'star', route: '/pages/study/deeptutor/skills/list' },
        { label: 'Memory', icon: 'heart', route: '/pages/study/deeptutor/memory/overview' },
        { label: 'Settings', icon: 'setting', route: '/pages/study/deeptutor/settings/index' },
      ],
    }
  },
  computed: {
    messages() {
      return this.chatStore.state.messages
    },
    sessionGroupTitle() {
      if (!this.recentSessions.length) return 'RECENT'
      const latest = this.recentSessions[0]?.updated_at
      if (!latest) return 'RECENT'
      const latestKey = dayjs(latest).format('YYYY-MM-DD')
      if (latestKey === dayjs().format('YYYY-MM-DD')) return 'TODAY'
      if (latestKey === dayjs().subtract(1, 'day').format('YYYY-MM-DD')) return 'YESTERDAY'
      return dayjs(latest).format('MMM DD').toUpperCase()
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
    },
    startNewChat() {
      this.chatStore.newSession()
      this.draft = ''
      this.showCapabilityMenu = false
    },
    async openSession(id) {
      try {
        await this.chatStore.loadSession(id)
        this.showCapabilityMenu = false
        this.scrollToBottom()
      } catch (e) {
        uni.showToast({ title: 'Failed to open session', icon: 'none' })
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
  background: rgba(248, 250, 255, 0.95);
  border-bottom: 1rpx solid rgba(148, 163, 184, 0.18);
  padding: 28rpx 24rpx 32rpx;
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
  background: linear-gradient(135deg, #38bdf8 0%, #60a5fa 100%);
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
  height: 84rpx;
  border-radius: 22rpx;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  color: #ffffff;
  border: none;
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
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
  border-radius: 18rpx;
  padding: 0 20rpx;
  display: flex;
  align-items: center;
  gap: 12rpx;
  background: rgba(56, 189, 248, 0.12);
  color: #0f172a;
  font-size: 26rpx;
}

.main-panel {
  flex: 1;
  padding: 24rpx 24rpx 40rpx;
  display: flex;
  flex-direction: column;
  min-height: 0;
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
  border: 1rpx solid rgba(56, 189, 248, 0.18);
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
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
  background: rgba(255, 255, 255, 0.96);
  padding: 24rpx 30rpx;
  border-radius: 20rpx 20rpx 20rpx 4rpx;
  font-size: 28rpx;
  color: #1f2937;
  line-height: 1.6;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.msg-bottom {
  height: 20rpx;
}

.composer-card {
  width: 100%;
  max-width: 1100rpx;
  align-self: center;
  border-radius: 34rpx;
  background: rgba(255, 255, 255, 0.95);
  border: 1rpx solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 24rpx 60rpx rgba(30, 64, 175, 0.08);
  overflow: hidden;
}

.capability-menu {
  margin: 22rpx 22rpx 0;
  border-radius: 26rpx;
  overflow: hidden;
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18rpx 40rpx rgba(15, 23, 42, 0.08);
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
  background: rgba(56, 189, 248, 0.14);
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
  background: #38bdf8;
  flex-shrink: 0;
}

.composer-textarea {
  width: 100%;
  min-height: 180rpx;
  max-height: 320rpx;
  padding: 34rpx 34rpx 22rpx;
  color: #0f172a;
  font-size: 32rpx;
  line-height: 1.65;
  background: transparent;
  box-sizing: border-box;
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
  justify-content: space-between;
  gap: 16rpx;
  flex-wrap: wrap;
}

.left-actions {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
}

.capability-pill,
.tool-pill {
  display: flex;
  align-items: center;
  gap: 10rpx;
  height: 64rpx;
  padding: 0 20rpx;
  border-radius: 999rpx;
  background: rgba(56, 189, 248, 0.12);
  color: #0f172a;
  font-size: 24rpx;
  border: 1rpx solid rgba(56, 189, 248, 0.18);
}

.capability-pill.active {
  background: rgba(56, 189, 248, 0.22);
  border-color: rgba(56, 189, 248, 0.28);
  color: #0f172a;
  box-shadow: inset 0 0 0 2rpx rgba(56, 189, 248, 0.12);
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-left: auto;
}

.model-pill {
  flex: 0 0 auto;
  min-width: 0;
  height: 64rpx;
  border-radius: 18rpx;
  padding: 0 18rpx;
  background: rgba(255, 255, 255, 0.9);
  color: #0f172a;
  font-size: 24rpx;
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.send-button {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  display: flex;
  align-items: center;
  justify-content: center;
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
    border-right: 1rpx solid rgba(148, 163, 184, 0.18);
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
    min-height: 160rpx;
    font-size: 28rpx;
  }

  .composer-toolbar {
    align-items: stretch;
  }

  .left-actions {
    width: 100%;
  }

  .composer-actions {
    width: 100%;
    justify-content: space-between;
    margin-left: 0;
  }

  .model-pill {
    width: 100%;
  }
}
</style>
