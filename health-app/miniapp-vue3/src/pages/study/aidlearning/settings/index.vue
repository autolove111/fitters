<template>
  <view class="settings-page">
    <text class="page-title">Settings</text>

    <view class="settings-group">
      <view class="setting-item" @click="go('/pages/study/aidlearning/settings/status')">
        <u-icon name="info-circle" size="36" color="#4f46e5" />
        <text>System Status</text>
        <u-icon name="arrow-right" size="28" color="#d1d5db" />
      </view>

      <view class="setting-item" @click="go('/pages/study/aidlearning/settings/llm')">
        <u-icon name="setting" size="36" color="#10b981" />
        <text>Model Catalog</text>
        <u-icon name="arrow-right" size="28" color="#d1d5db" />
      </view>

      <view class="setting-item" @click="go('/pages/study/aidlearning/settings/tools')">
        <u-icon name="list" size="36" color="#f59e0b" />
        <text>Tools</text>
        <u-icon name="arrow-right" size="28" color="#d1d5db" />
      </view>

      <view class="setting-item" @click="go('/pages/study/aidlearning/settings/appearance')">
        <u-icon name="photo" size="36" color="#8b5cf6" />
        <text>Appearance</text>
        <u-icon name="arrow-right" size="28" color="#d1d5db" />
      </view>

      <view class="setting-item" @click="go('/pages/study/aidlearning/history/list')">
        <u-icon name="clock" size="36" color="#6366f1" />
        <text>Chat History</text>
        <u-icon name="arrow-right" size="28" color="#d1d5db" />
      </view>

      <view v-if="userStore.state.isAdmin" class="setting-item" @click="go('/pages/study/aidlearning/settings/users')">
        <u-icon name="account" size="36" color="#ef4444" />
        <text>Users</text>
        <u-icon name="arrow-right" size="28" color="#d1d5db" />
      </view>
    </view>

    <view class="settings-group">
      <view class="setting-item api-row" @click="handleApiBase">
        <u-icon name="empty-address" size="36" color="#6b7280" />
        <view class="api-copy">
          <text>API Base</text>
          <text class="setting-value">{{ apiBase }}</text>
        </view>
      </view>
    </view>

    <u-button type="error" plain shape="circle" @click="handleLogout">Logout</u-button>
  </view>
</template>

<script>
import { useUserStore } from '../../store/user'
import { getApiBase, setApiBase } from '../../utils/api'

export default {
  data() {
    return {
      userStore: useUserStore(),
      apiBase: getApiBase(),
    }
  },
  methods: {
    go(url) {
      uni.navigateTo({ url })
    },
    handleLogout() {
      uni.showModal({
        title: 'Logout',
        content: 'Do you want to log out?',
        success: (res) => {
          if (res.confirm) this.userStore.logout()
        },
      })
    },
    handleApiBase() {
      uni.showModal({
        title: 'Set API Base',
        editable: true,
        placeholderText: this.apiBase,
        success: (res) => {
          if (res.confirm && res.content) {
            setApiBase(res.content)
            this.apiBase = res.content
            uni.showToast({ title: 'Updated', icon: 'success' })
          }
        },
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.settings-page {
  min-height: 100vh;
  padding: 30rpx;
  background: #f6f1eb;
}

.page-title {
  display: block;
  margin-bottom: 30rpx;
  font-size: 40rpx;
  font-weight: 700;
  color: #2e221b;
}

.settings-group {
  margin-bottom: 24rpx;
  overflow: hidden;
  border-radius: 20rpx;
  background: #fffaf6;
  box-shadow: 0 10rpx 24rpx rgba(58, 38, 22, 0.08);
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 28rpx 30rpx;
  border-bottom: 1rpx solid #f1e3d7;
  font-size: 30rpx;
  color: #2e221b;
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item text:nth-child(2) {
  flex: 1;
}

.api-row {
  align-items: flex-start;
}

.api-copy {
  flex: 1;
  min-width: 0;
}

.setting-value {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  line-height: 1.5;
  color: #8c7664;
  word-break: break-all;
}
</style>
