<template>
  <view class="appearance-page">
    <text class="page-title">外观设置</text>
    <view class="section">
      <text class="section-title">主题</text>
      <view class="theme-list">
        <view v-for="t in themes" :key="t" class="theme-item" :class="{ active: currentTheme === t }" @click="setTheme(t)">
          <text>{{ t }}</text>
        </view>
      </view>
    </view>
    <view class="section">
      <text class="section-title">语言</text>
      <view class="theme-list">
        <view class="theme-item" :class="{ active: currentLang === 'zh' }" @click="setLang('zh')"><text>中文</text></view>
        <view class="theme-item" :class="{ active: currentLang === 'en' }" @click="setLang('en')"><text>English</text></view>
      </view>
    </view>
  </view>
</template>

<script>
import { useSettingsStore } from '../../store/settings'

export default {
  data() {
    return {
      settingsStore: useSettingsStore(),
      themes: ['light', 'dark'],
      currentTheme: 'light',
      currentLang: 'zh',
    }
  },
  onShow() {
    this.currentTheme = this.settingsStore.state.theme
    this.currentLang = this.settingsStore.state.language
  },
  methods: {
    async setTheme(t) {
      this.currentTheme = t
      try { await this.settingsStore.updateTheme(t) } catch (e) {}
    },
    async setLang(l) {
      this.currentLang = l
      try { await this.settingsStore.updateLanguage(l) } catch (e) {}
    },
  },
}
</script>

<style lang="scss" scoped>
.appearance-page { padding: 30rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; display: block; margin-bottom: 30rpx; }
.section { background: #fff; border-radius: 16rpx; padding: 30rpx; margin-bottom: 24rpx; }
.section-title { font-size: 30rpx; font-weight: 600; display: block; margin-bottom: 20rpx; }
.theme-list { display: flex; gap: 16rpx; flex-wrap: wrap; }
.theme-item {
  padding: 16rpx 32rpx; border: 2rpx solid #e5e7eb; border-radius: 12rpx;
  font-size: 28rpx; color: #374151;
  &.active { border-color: #4f46e5; color: #4f46e5; background: #eef2ff; }
}
</style>
