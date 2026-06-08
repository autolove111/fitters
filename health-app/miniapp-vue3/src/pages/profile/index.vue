<template>
  <view class="profile-page" :class="{ dark: isDark }">
    <!-- 头像 -->
    <view class="profile-card">
      <view class="profile-item" @click="onAvatarClick">
        <text class="item-label">头像</text>
        <view class="item-right">
          <image v-if="avatar" class="avatar-img" :src="avatar" mode="aspectFill" />
          <view v-else class="avatar-placeholder">
            <text class="avatar-placeholder-text">{{ (nickname || username || '?')[0] }}</text>
          </view>
          <text class="item-arrow">›</text>
        </view>
      </view>

      <!-- 昵称 -->
      <view class="profile-item" @click="showNicknameEdit = true">
        <text class="item-label">昵称</text>
        <view class="item-right">
          <text class="item-value">{{ nickname || username || '未设置' }}</text>
          <text class="item-arrow">›</text>
        </view>
      </view>

      <!-- 修改密码 -->
      <view class="profile-item" @click="goChangePassword">
        <text class="item-label">修改密码</text>
        <view class="item-right">
          <text class="item-arrow">›</text>
        </view>
      </view>

      <!-- 深色模式 -->
      <view class="profile-item">
        <text class="item-label">深色模式</text>
        <view class="item-right">
          <view class="theme-toggle" :class="{ active: isDark }" @click="onToggleTheme">
            <view class="toggle-knob"></view>
          </view>
        </view>
      </view>
    </view>

    <!-- 退出 & 注销 -->
    <view class="profile-card">
      <view class="profile-item" @click="confirmLogout">
        <text class="item-label">退出登录</text>
        <view class="item-right">
          <text class="item-arrow">›</text>
        </view>
      </view>
      <view class="profile-item danger" @click="confirmDelete">
        <text class="item-label danger-text">注销账号</text>
        <view class="item-right">
          <text class="item-arrow">›</text>
        </view>
      </view>
    </view>

    <!-- 昵称编辑弹窗 -->
    <view v-if="showNicknameEdit" class="modal-mask" @click="showNicknameEdit = false">
      <view class="modal-card" @click.stop>
        <text class="modal-title">修改昵称</text>
        <input class="modal-input" v-model="nicknameInput" placeholder="请输入昵称" maxlength="20" />
        <view class="modal-actions">
          <button class="modal-btn cancel" @click="showNicknameEdit = false">取消</button>
          <button class="modal-btn confirm" @click="saveNickname">确定</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useUserStore } from '@/store/user'
import { useThemeStore } from '@/store/theme'
import { userApi } from '@/utils/api'

const userStore = useUserStore()
const { state, displayName, saveAvatar, saveNickname: storeSaveNickname, clearUser } = userStore

const themeStore = useThemeStore()
const { isDark, toggleTheme } = themeStore

const onToggleTheme = () => {
  toggleTheme()
}

const avatar = computed(() => state.avatar || '')
const nickname = computed(() => state.nickname || '')
const username = computed(() => state.username || '')

const showNicknameEdit = ref(false)
const nicknameInput = ref(state.nickname || '')

// 头像点击
const onAvatarClick = () => {
  uni.showActionSheet({
    itemList: ['查看头像', '更换头像'],
    success: (res) => {
      if (res.tapIndex === 0) {
        viewAvatar()
      } else if (res.tapIndex === 1) {
        pickAvatar()
      }
    }
  })
}

const viewAvatar = () => {
  if (!avatar.value) {
    uni.showToast({ title: '暂无头像', icon: 'none' })
    return
  }
  uni.previewImage({ urls: [avatar.value], current: avatar.value })
}

const pickAvatar = () => {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['album', 'camera'],
    success: async (res) => {
      try {
        await saveAvatar(res.tempFilePaths[0])
        uni.showToast({ title: '头像已更新', icon: 'success' })
      } catch (e) {
        uni.showToast({ title: '头像上传失败，请重试', icon: 'none' })
      }
    }
  })
}

// 保存昵称
const saveNickname = async () => {
  const val = nicknameInput.value.trim()
  if (!val) {
    uni.showToast({ title: '昵称不能为空', icon: 'none' })
    return
  }
  await storeSaveNickname(val)
  showNicknameEdit.value = false
  uni.showToast({ title: '昵称已更新', icon: 'success' })
}

// 修改密码
const goChangePassword = () => {
  uni.navigateTo({ url: '/pages/profile/password' })
}

// 退出登录
const confirmLogout = () => {
  uni.showModal({
    title: '确认退出',
    content: '确定要退出登录吗？',
    success: (res) => {
      if (res.confirm) {
        clearUser()
        uni.reLaunch({ url: '/pages/index/index' })
      }
    }
  })
}

// 注销账号
const confirmDelete = () => {
  uni.showModal({
    title: '注销账号',
    content: '注销后账号数据将无法恢复，确定要注销吗？',
    confirmColor: '#e53935',
    success: async (res) => {
      if (res.confirm) {
        try {
          await userApi.deleteAccount()
          clearUser()
          uni.reLaunch({ url: '/pages/index/index' })
          uni.showToast({ title: '账号已注销', icon: 'none' })
        } catch (e) {
          uni.showToast({ title: '注销失败，请重试', icon: 'none' })
        }
      }
    }
  })
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
  padding: 32rpx;
}
.profile-card {
  background: var(--card-bg);
  border-radius: 36rpx;
  margin-bottom: 28rpx;
  overflow: hidden;
  border: 1rpx solid var(--card-border);
  box-shadow: 0 20rpx 44rpx var(--card-shadow);
}
.profile-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 30rpx;
  border-bottom: 1rpx solid var(--divider);
}
.profile-item:last-child {
  border-bottom: none;
}
.item-label {
  font-size: 30rpx;
  color: var(--text-primary);
}
.item-right {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.item-value {
  font-size: 28rpx;
  color: var(--text-secondary);
}
.item-arrow {
  font-size: 36rpx;
  color: var(--text-tertiary);
}
.avatar-img {
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
}
.avatar-placeholder {
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #38bdf8, #22c55e);
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar-placeholder-text {
  font-size: 36rpx;
  color: #ffffff;
  font-weight: 700;
}
.danger:active {
  background: var(--danger-bg);
}
.danger-text {
  color: var(--danger-color);
}

/* 主题切换开关 */
.theme-toggle {
  width: 96rpx;
  height: 52rpx;
  border-radius: 999rpx;
  background: var(--toggle-bg);
  position: relative;
  transition: background 0.3s;
}
.theme-toggle.active {
  background: var(--toggle-active-bg);
}
.toggle-knob {
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  background: #ffffff;
  position: absolute;
  top: 4rpx;
  left: 4rpx;
  transition: transform 0.3s;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.15);
}
.theme-toggle.active .toggle-knob {
  transform: translateX(44rpx);
}

/* 弹窗 */
.modal-mask {
  position: fixed;
  inset: 0;
  background: var(--overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}
.modal-card {
  width: 600rpx;
  background: var(--modal-bg);
  border-radius: 36rpx;
  padding: 40rpx;
}
.modal-title {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--text-primary);
  display: block;
  text-align: center;
  margin-bottom: 30rpx;
}
.modal-input {
  height: 88rpx;
  border: 1rpx solid var(--input-border);
  border-radius: 24rpx;
  padding: 0 24rpx;
  font-size: 30rpx;
  margin-bottom: 30rpx;
  color: var(--text-primary);
}
.modal-actions {
  display: flex;
  gap: 20rpx;
}
.modal-btn {
  flex: 1;
  height: 80rpx;
  border-radius: 999rpx;
  font-size: 28rpx;
  font-weight: 600;
  border: none;
}
.modal-btn.cancel {
  background: var(--btn-cancel-bg);
  color: var(--btn-cancel-text);
}
.modal-btn.confirm {
  background: linear-gradient(90deg, #38bdf8, #22c55e);
  color: #ffffff;
}
</style>
