<template>
  <view class="users-page">
    <text class="page-title">用户管理</text>
    <view v-if="loading" class="loading"><u-loading-icon /></view>
    <template v-else>
      <view class="user-list">
        <view v-for="u in users" :key="u.username || u.user_id" class="user-card">
          <view class="user-info">
            <text class="user-name">{{ u.username }}</text>
            <u-tag :text="u.role || 'user'" :type="u.role === 'admin' ? 'error' : 'info'" plain size="mini" />
          </view>
          <view class="user-actions">
            <u-button size="small" type="primary" plain @click="toggleRole(u)">{{ u.role === 'admin' ? '设为用户' : '设为管理员' }}</u-button>
            <u-button size="small" type="error" plain @click="deleteUser(u)">删除</u-button>
          </view>
        </view>
      </view>
      <view v-if="users.length === 0" class="empty"><text>暂无用户</text></view>
    </template>
  </view>
</template>

<script>
import { authApi } from '../../api/auth'

export default {
  data() { return { users: [], loading: true } },
  onShow() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        const res = await authApi.listUsers()
        this.users = Array.isArray(res) ? res : res.users || []
      } catch (e) {}
      this.loading = false
    },
    async toggleRole(u) {
      const newRole = u.role === 'admin' ? 'user' : 'admin'
      try {
        await authApi.updateRole(u.username, newRole)
        this.load()
      } catch (e) {
        uni.showToast({ title: '操作失败', icon: 'none' })
      }
    },
    async deleteUser(u) {
      uni.showModal({
        title: '确认删除',
        content: `确定删除用户 "${u.username}"？`,
        success: async (res) => {
          if (res.confirm) {
            try {
              await authApi.deleteUser(u.username)
              this.load()
            } catch (e) {
              uni.showToast({ title: '删除失败', icon: 'none' })
            }
          }
        },
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.users-page { padding: 30rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; display: block; margin-bottom: 30rpx; }
.loading { display: flex; justify-content: center; padding: 100rpx 0; }
.user-card {
  background: #fff; border-radius: 16rpx; padding: 24rpx; margin-bottom: 16rpx;
}
.user-info { display: flex; align-items: center; gap: 16rpx; margin-bottom: 16rpx; }
.user-name { font-size: 30rpx; font-weight: 600; color: #1f2937; }
.user-actions { display: flex; gap: 16rpx; }
.empty { text-align: center; padding: 100rpx 0; color: #9ca3af; }
</style>
