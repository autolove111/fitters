<template>
  <view class="doc-page">
    <view v-if="loading" class="loading"><u-loading-icon /></view>
    <template v-else>
      <view class="doc-header">
        <text class="doc-title">{{ layer }} / {{ key }}</text>
      </view>
      <u-textarea v-model="content" placeholder="文档内容" maxlength="-1" autoHeight border="surround" />
      <view class="actions">
        <u-button type="primary" shape="circle" :loading="saving" @click="save">保存</u-button>
        <u-button type="error" plain shape="circle" @click="reset">重置</u-button>
      </view>
    </template>
  </view>
</template>

<script>
import { memoryApi } from '../../api/memory'

export default {
  data() {
    return { layer: '', key: '', content: '', loading: true, saving: false }
  },
  onLoad(query) {
    this.layer = query.layer
    this.key = query.key
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      try {
        const res = await memoryApi.getDoc(this.layer, this.key)
        this.content = res.content || res || ''
      } catch (e) {
        uni.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    async save() {
      this.saving = true
      try {
        await memoryApi.saveDoc(this.layer, this.key, this.content)
        uni.showToast({ title: '已保存', icon: 'success' })
      } catch (e) {
        uni.showToast({ title: '保存失败', icon: 'none' })
      } finally {
        this.saving = false
      }
    },
    reset() {
      uni.showModal({
        title: '确认重置',
        content: '将清除文档所有内容',
        success: async (res) => {
          if (res.confirm) {
            try {
              await memoryApi.resetDoc(this.layer, this.key)
              this.content = ''
              uni.showToast({ title: '已重置', icon: 'success' })
            } catch (e) {
              uni.showToast({ title: '操作失败', icon: 'none' })
            }
          }
        },
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.doc-page { padding: 30rpx; }
.loading { display: flex; justify-content: center; padding: 100rpx 0; }
.doc-header { margin-bottom: 30rpx; }
.doc-title { font-size: 32rpx; font-weight: 600; color: #1f2937; }
.actions { display: flex; flex-direction: column; gap: 20rpx; margin-top: 30rpx; }
</style>
