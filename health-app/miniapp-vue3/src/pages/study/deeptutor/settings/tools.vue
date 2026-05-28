<template>
  <view class="tools-page">
    <text class="page-title">工具管理</text>
    <view v-if="loading" class="loading"><u-loading-icon /></view>
    <template v-else>
      <view v-for="tool in tools" :key="tool.name" class="tool-item">
        <view class="tool-info">
          <text class="tool-name">{{ tool.name }}</text>
          <text class="tool-desc">{{ tool.description || '' }}</text>
        </view>
        <u-switch v-model="tool.enabled" @change="toggleTool(tool)" />
      </view>
      <view v-if="tools.length === 0" class="empty"><text>暂无工具</text></view>
    </template>
  </view>
</template>

<script>
import { useSettingsStore } from '../../store/settings'

export default {
  data() {
    return { tools: [], loading: true, settingsStore: useSettingsStore() }
  },
  onShow() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        const res = await this.settingsStore.loadTools()
        this.tools = (res.tools || []).map((t) => ({ ...t, enabled: t.enabled !== false }))
      } catch (e) {}
      this.loading = false
    },
    async toggleTool(tool) {
      const enabled = this.tools.filter((t) => t.enabled).map((t) => t.name)
      try {
        await this.settingsStore.updateEnabledTools(enabled)
      } catch (e) {
        uni.showToast({ title: '更新失败', icon: 'none' })
      }
    },
  },
}
</script>

<style lang="scss" scoped>
.tools-page { padding: 30rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; display: block; margin-bottom: 30rpx; }
.loading { display: flex; justify-content: center; padding: 100rpx 0; }
.tool-item {
  background: #fff; border-radius: 12rpx; padding: 24rpx; margin-bottom: 12rpx;
  display: flex; align-items: center; justify-content: space-between;
}
.tool-info { flex: 1; margin-right: 20rpx; }
.tool-name { display: block; font-size: 28rpx; font-weight: 500; color: #1f2937; }
.tool-desc { display: block; font-size: 24rpx; color: #9ca3af; margin-top: 6rpx; }
.empty { text-align: center; padding: 100rpx 0; color: #9ca3af; }
</style>
