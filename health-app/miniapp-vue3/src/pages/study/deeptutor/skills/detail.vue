<template>
  <view class="skill-detail">
    <text class="page-title">{{ isCreate ? '创建技能' : '编辑技能' }}</text>
    <u-input v-model="form.name" placeholder="技能名称" border="surround" :disabled="!isCreate" />
    <u-input v-model="form.description" placeholder="描述" border="surround" />
    <u-textarea v-model="form.content" placeholder="技能内容 / Prompt" maxlength="-1" autoHeight border="surround" />
    <u-input v-model="tagsStr" placeholder="标签 (逗号分隔)" border="surround" />
    <view class="actions">
      <u-button type="primary" shape="circle" :loading="saving" @click="handleSave">{{ isCreate ? '创建' : '保存' }}</u-button>
      <u-button v-if="!isCreate" type="error" plain shape="circle" @click="handleDelete">删除</u-button>
    </view>
  </view>
</template>

<script>
import { skillsApi } from '../../api/skills'

export default {
  data() {
    return {
      isCreate: false,
      originalName: '',
      form: { name: '', description: '', content: '', tags: [] },
      tagsStr: '',
      saving: false,
    }
  },
  async onLoad(query) {
    this.isCreate = query.mode === 'create'
    if (!this.isCreate && query.name) {
      this.originalName = query.name
      try {
        const res = await skillsApi.get(query.name)
        this.form = { name: res.name, description: res.description || '', content: res.content || '', tags: res.tags || [] }
        this.tagsStr = (res.tags || []).join(', ')
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      }
    }
  },
  methods: {
    async handleSave() {
      this.saving = true
      try {
        const tags = this.tagsStr.split(',').map((t) => t.trim()).filter(Boolean)
        if (this.isCreate) {
          await skillsApi.create({ ...this.form, tags })
        } else {
          await skillsApi.update(this.originalName, { description: this.form.description, content: this.form.content, tags })
        }
        uni.showToast({ title: '保存成功', icon: 'success' })
        setTimeout(() => uni.navigateBack(), 1000)
      } catch (e) {
        uni.showToast({ title: e.message || '保存失败', icon: 'none' })
      } finally {
        this.saving = false
      }
    },
    async handleDelete() {
      uni.showModal({
        title: '确认删除',
        content: `确定删除技能 "${this.originalName}"？`,
        success: async (res) => {
          if (res.confirm) {
            try {
              await skillsApi.delete(this.originalName)
              uni.showToast({ title: '已删除', icon: 'success' })
              uni.navigateBack()
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
.skill-detail { padding: 30rpx; display: flex; flex-direction: column; gap: 24rpx; }
.page-title { font-size: 36rpx; font-weight: 700; color: #1f2937; }
.actions { display: flex; flex-direction: column; gap: 20rpx; margin-top: 10rpx; }
</style>
