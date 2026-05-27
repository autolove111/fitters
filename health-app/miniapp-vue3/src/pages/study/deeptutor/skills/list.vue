<template>
  <view class="skills-page">
    <view class="header">
      <text class="page-title">技能</text>
      <u-button type="primary" size="small" shape="circle" @click="goCreate">新建</u-button>
    </view>
    <view v-if="loading" class="loading"><u-loading-icon /></view>
    <view v-else-if="list.length === 0" class="empty">
      <u-icon name="star" size="80" color="#d1d5db" />
      <text>暂无技能</text>
    </view>
    <view v-for="skill in list" :key="skill.name" class="skill-card" @click="goDetail(skill.name)">
      <SkillCard :skill="skill" />
    </view>
  </view>
</template>

<script>
import { skillsApi } from '../../api/skills'
import SkillCard from '../../components/SkillCard.vue'

export default {
  components: { SkillCard },
  data() {
    return { list: [], loading: true }
  },
  onShow() { this.load() },
  methods: {
    async load() {
      this.loading = true
      try {
        const res = await skillsApi.list()
        this.list = Array.isArray(res) ? res : res.skills || []
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    goCreate() { uni.navigateTo({ url: '/pages/study/deeptutor/skills/detail?mode=create' }) },
    goDetail(name) { uni.navigateTo({ url: `/pages/study/deeptutor/skills/detail?name=${name}` }) },
  },
}
</script>

<style lang="scss" scoped>
.skills-page { padding: 30rpx; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; }
.loading { display: flex; justify-content: center; padding: 100rpx 0; }
.empty { display: flex; flex-direction: column; align-items: center; padding: 100rpx 0; color: #9ca3af; font-size: 28rpx; }
.skill-card { margin-bottom: 16rpx; }
</style>
