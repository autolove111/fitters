<template>
  <view class="detail-page">
    <view class="top-deco" />

    <view class="page-header">
      <view class="header-left">
        <view class="header-accent" />
        <text class="page-title">{{ isCreate ? '创建技能' : '编辑技能' }}</text>
      </view>
    </view>

    <view class="form-section">
      <view class="input-group">
        <text class="input-label">名称</text>
        <view class="input-wrap">
          <u-input v-model="form.name" placeholder="技能名称" border="none" :disabled="!isCreate" :customStyle="{ color: '#0f172a' }" />
        </view>
      </view>

      <view class="input-group">
        <text class="input-label">描述</text>
        <view class="input-wrap">
          <u-input v-model="form.description" placeholder="简要描述这个技能" border="none" :customStyle="{ color: '#0f172a' }" />
        </view>
      </view>

      <view class="input-group">
        <text class="input-label">内容 / Prompt</text>
        <view class="textarea-wrap">
          <u-textarea v-model="form.content" placeholder="输入技能的详细内容或 Prompt..." maxlength="-1" autoHeight border="none" :customStyle="{ color: '#0f172a', background: 'transparent' }" />
        </view>
      </view>

      <view class="input-group">
        <text class="input-label">标签</text>
        <view class="input-wrap">
          <u-input v-model="tagsStr" placeholder="多个标签用逗号分隔" border="none" :customStyle="{ color: '#0f172a' }" />
        </view>
      </view>

      <view class="btn-save" :class="{ disabled: saving }" @click="handleSave">
        <u-loading-icon v-if="saving" size="28" color="#ffffff" />
        <text v-else>{{ isCreate ? '创建技能' : '保存修改' }}</text>
      </view>

      <view v-if="!isCreate" class="btn-delete" @click="handleDelete">
        <u-icon name="trash" size="26" color="#ef4444" />
        <text>删除技能</text>
      </view>
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
      if (this.saving) return
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
.detail-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f0f7ff 0%, #f8fbff 30%, #ffffff 100%);
  padding: 0 28rpx 60rpx;
  position: relative;
}

.top-deco {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 260rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(20, 184, 166, 0.06));
  border-radius: 0 0 60rpx 60rpx;
}

.page-header {
  position: relative;
  padding: 32rpx 0 28rpx;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.header-accent {
  width: 8rpx;
  height: 36rpx;
  border-radius: 4rpx;
  background: linear-gradient(180deg, #f59e0b, #fbbf24);
}

.page-title {
  font-size: 38rpx;
  font-weight: 700;
  color: #0f172a;
}

.form-section {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 28rpx;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.input-label {
  font-size: 26rpx;
  font-weight: 600;
  color: #334155;
}

.input-wrap {
  background: #ffffff;
  border-radius: 20rpx;
  padding: 4rpx 24rpx;
  box-shadow: 0 4rpx 16rpx rgba(15, 23, 42, 0.04);
  border: 1rpx solid rgba(14, 165, 233, 0.08);
}

.textarea-wrap {
  background: #ffffff;
  border-radius: 20rpx;
  padding: 16rpx 24rpx;
  min-height: 240rpx;
  box-shadow: 0 4rpx 16rpx rgba(15, 23, 42, 0.04);
  border: 1rpx solid rgba(14, 165, 233, 0.08);
}

.btn-save {
  height: 88rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #f59e0b, #fbbf24);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 600;
  margin-top: 12rpx;
  box-shadow: 0 16rpx 32rpx rgba(245, 158, 11, 0.25);

  &.disabled {
    opacity: 0.5;
  }
}

.btn-delete {
  height: 84rpx;
  border-radius: 20rpx;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  color: #ef4444;
  font-size: 28rpx;
  font-weight: 600;
  border: 2rpx solid rgba(239, 68, 68, 0.15);
}
</style>
