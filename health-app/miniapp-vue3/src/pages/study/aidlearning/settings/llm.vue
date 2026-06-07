<template>
  <view class="llm-page">
    <text class="page-title">Model Catalog</text>
    <text class="page-subtitle">Configure the active LLM and Embedding profiles.</text>

    <view v-if="loading" class="loading">
      <u-loading-icon />
    </view>

    <template v-else>
      <!-- LLM Panel -->
      <view class="panel">
        <text class="section-title">Active LLM</text>

        <view class="field">
          <text class="field-label">Provider</text>
          <picker
            mode="selector"
            :range="providerLabels"
            :value="providerIndex"
            @change="handleProviderChange"
          >
            <view class="picker-field">
              <text>{{ providerLabels[providerIndex] || 'Select provider' }}</text>
              <u-icon name="arrow-down" size="20" color="#8b735f" />
            </view>
          </picker>
        </view>

        <view class="field">
          <text class="field-label">Profile Name</text>
          <input
            v-model="form.profileName"
            class="text-input"
            placeholder="OpenAI / Ollama / DeepSeek"
          />
        </view>

        <view class="field">
          <view class="field-header">
            <text class="field-label">Base URL</text>
            <text class="field-tip" @click="fillProviderDefaultUrl">Use default</text>
          </view>
          <input
            v-model="form.baseUrl"
            class="text-input"
            placeholder="https://api.openai.com/v1"
          />
        </view>

        <view class="field">
          <text class="field-label">API Key</text>
          <input
            v-model="form.apiKey"
            class="text-input"
            password
            placeholder="sk-..."
          />
        </view>

        <view class="field">
          <text class="field-label">Model ID</text>
          <input
            v-model="form.modelId"
            class="text-input"
            placeholder="gpt-4o-mini / deepseek-chat / qwen2.5:7b"
          />
        </view>

        <view class="field">
          <text class="field-label">Model Name</text>
          <input
            v-model="form.modelName"
            class="text-input"
            placeholder="Shown in the UI"
          />
        </view>
      </view>

      <!-- Embedding Panel -->
      <view class="panel">
        <text class="section-title">Active Embedding</text>
        <text class="section-desc">Used for knowledge base vectorization. Required for reindex.</text>

        <view class="field">
          <text class="field-label">Provider</text>
          <picker
            mode="selector"
            :range="embeddingProviderLabels"
            :value="embeddingProviderIndex"
            @change="handleEmbeddingProviderChange"
          >
            <view class="picker-field">
              <text>{{ embeddingProviderLabels[embeddingProviderIndex] || 'Select provider' }}</text>
              <u-icon name="arrow-down" size="20" color="#8b735f" />
            </view>
          </picker>
        </view>

        <view class="field">
          <text class="field-label">Profile Name</text>
          <input
            v-model="embForm.profileName"
            class="text-input"
            placeholder="Embedding Profile"
          />
        </view>

        <view class="field">
          <view class="field-header">
            <text class="field-label">Base URL</text>
            <text class="field-tip" @click="fillEmbeddingDefaultUrl">Use default</text>
          </view>
          <input
            v-model="embForm.baseUrl"
            class="text-input"
            placeholder="https://api.openai.com/v1"
          />
        </view>

        <view class="field">
          <text class="field-label">API Key</text>
          <input
            v-model="embForm.apiKey"
            class="text-input"
            password
            placeholder="sk-..."
          />
        </view>

        <view class="field">
          <text class="field-label">Model ID</text>
          <input
            v-model="embForm.modelId"
            class="text-input"
            placeholder="text-embedding-3-small / bge-m3"
          />
        </view>

        <view class="field">
          <text class="field-label">Model Name</text>
          <input
            v-model="embForm.modelName"
            class="text-input"
            placeholder="Shown in the UI"
          />
        </view>
      </view>

      <view class="action-row">
        <u-button
          class="action-btn"
          color="#7b5b46"
          shape="circle"
          :loading="saving"
          @click="saveCatalog"
        >
          Save
        </u-button>
        <u-button
          class="action-btn"
          color="#c98b4a"
          shape="circle"
          :loading="applying"
          @click="applyCatalog"
        >
          Apply
        </u-button>
      </view>

      <view class="action-row single">
        <u-button
          class="action-btn"
          plain
          shape="circle"
          color="#8b735f"
          :loading="testing"
          @click="testConnection"
        >
          Test LLM
        </u-button>
        <u-button
          class="action-btn"
          plain
          shape="circle"
          color="#8b735f"
          :loading="testingEmb"
          @click="testEmbedding"
        >
          Test Embedding
        </u-button>
      </view>

      <view v-if="testResult" class="panel result-panel">
        <view class="result-head">
          <text class="section-title">Test Result</text>
          <text :class="['result-badge', testResult.success ? 'ok' : 'fail']">
            {{ testResult.success ? 'Success' : 'Failed' }}
          </text>
        </view>
        <text class="result-line">{{ testResult.message || '-' }}</text>
        <text v-if="testResult.model" class="result-line">Model: {{ testResult.model }}</text>
        <text v-if="testResult.response_time_ms" class="result-line">
          Response: {{ testResult.response_time_ms }} ms
        </text>
        <text v-if="testResult.error" class="result-error">{{ testResult.error }}</text>
      </view>
    </template>
  </view>
</template>

<script>
import { useSettingsStore } from '../../store/settings'

const defaultCatalog = () => ({
  version: 1,
  services: {
    llm: {
      active_profile_id: null,
      active_model_id: null,
      profiles: [],
    },
    embedding: {
      active_profile_id: null,
      active_model_id: null,
      profiles: [],
    },
    search: {
      active_profile_id: null,
      profiles: [],
    },
  },
})

const clone = (value) => JSON.parse(JSON.stringify(value))

export default {
  data() {
    return {
      loading: true,
      saving: false,
      applying: false,
      testing: false,
      testingEmb: false,
      settingsStore: useSettingsStore(),
      catalogDraft: defaultCatalog(),
      providerOptions: [],
      providerIndex: 0,
      embeddingProviderOptions: [],
      embeddingProviderIndex: 0,
      testResult: null,
      form: {
        profileName: '',
        provider: 'openai',
        baseUrl: '',
        apiKey: '',
        modelId: '',
        modelName: '',
      },
      embForm: {
        profileName: '',
        provider: 'openai',
        baseUrl: '',
        apiKey: '',
        modelId: '',
        modelName: '',
      },
    }
  },
  computed: {
    providerLabels() {
      return this.providerOptions.map((item) => item.label)
    },
    selectedProvider() {
      return this.providerOptions[this.providerIndex] || null
    },
    embeddingProviderLabels() {
      return this.embeddingProviderOptions.map((item) => item.label)
    },
    selectedEmbeddingProvider() {
      return this.embeddingProviderOptions[this.embeddingProviderIndex] || null
    },
  },
  onShow() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.testResult = null
      try {
        const settings = await this.settingsStore.loadSettings()
        const catalog = settings.catalog || (await this.settingsStore.loadCatalog()) || defaultCatalog()
        this.catalogDraft = clone(catalog)
        this.providerOptions = settings.providers?.llm || []
        if (!this.providerOptions.length) {
          this.providerOptions = [
            { value: 'openai', label: 'OpenAI', base_url: 'https://api.openai.com/v1' },
          ]
        }
        this.embeddingProviderOptions = settings.providers?.embedding || []
        if (!this.embeddingProviderOptions.length) {
          this.embeddingProviderOptions = [
            { value: 'openai', label: 'OpenAI', base_url: 'https://api.openai.com/v1' },
            { value: 'siliconflow', label: 'SiliconFlow', base_url: 'https://api.siliconflow.cn/v1' },
            { value: 'aliyun', label: 'Aliyun DashScope', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          ]
        }
        this.syncFormFromCatalog()
      } catch (e) {
        uni.showToast({ title: e.message || 'Load failed', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    syncFormFromCatalog() {
      const catalog = this.catalogDraft?.services?.llm ? this.catalogDraft : defaultCatalog()

      // LLM
      const llmService = catalog.services.llm || {}
      const llmProfiles = llmService.profiles || []
      const llmProfile =
        llmProfiles.find((item) => item.id === llmService.active_profile_id) ||
        llmProfiles[0] ||
        {}
      const llmModels = llmProfile.models || []
      const llmModel =
        llmModels.find((item) => item.id === llmService.active_model_id) ||
        llmModels[0] ||
        {}

      const providerValue = llmProfile.binding || 'openai'
      let providerIndex = this.providerOptions.findIndex((item) => item.value === providerValue)
      if (providerIndex < 0) providerIndex = 0
      this.providerIndex = providerIndex

      const selected = this.providerOptions[providerIndex] || {}
      const fallbackModelId = selected.value === 'ollama' ? 'qwen2.5:7b' : 'gpt-4o-mini'
      const modelId = llmModel.model || ''
      const modelName = llmModel.name || modelId || fallbackModelId

      this.form = {
        profileName: llmProfile.name || selected.label || 'LLM Profile',
        provider: providerValue,
        baseUrl: llmProfile.base_url || selected.base_url || '',
        apiKey: llmProfile.api_key || '',
        modelId: modelId || fallbackModelId,
        modelName,
      }

      // Embedding
      const embService = catalog.services.embedding || {}
      const embProfiles = embService.profiles || []
      const embProfile =
        embProfiles.find((item) => item.id === embService.active_profile_id) ||
        embProfiles[0] ||
        null

      if (embProfile) {
        const embModels = embProfile.models || []
        const embModel =
          embModels.find((item) => item.id === embService.active_model_id) ||
          embModels[0] ||
          {}
        const embProviderValue = embProfile.binding || 'openai'
        let embProviderIndex = this.embeddingProviderOptions.findIndex((item) => item.value === embProviderValue)
        if (embProviderIndex < 0) embProviderIndex = 0
        this.embeddingProviderIndex = embProviderIndex

        this.embForm = {
          profileName: embProfile.name || 'Embedding Profile',
          provider: embProviderValue,
          baseUrl: embProfile.base_url || '',
          apiKey: embProfile.api_key || '',
          modelId: embModel.model || '',
          modelName: embModel.name || '',
        }
      } else {
        // Default to first embedding provider option
        this.embeddingProviderIndex = 0
        const defaultEmb = this.embeddingProviderOptions[0] || {}
        this.embForm = {
          profileName: '',
          provider: defaultEmb.value || 'openai',
          baseUrl: '',
          apiKey: '',
          modelId: '',
          modelName: '',
        }
      }
    },
    handleProviderChange(event) {
      const index = Number(event.detail.value || 0)
      this.providerIndex = index
      const selected = this.providerOptions[index] || {}
      this.form.provider = selected.value || 'openai'
      if (!this.form.profileName || this.form.profileName === 'LLM Profile') {
        this.form.profileName = selected.label || 'LLM Profile'
      }
      if (!this.form.baseUrl) {
        this.form.baseUrl = selected.base_url || ''
      }
    },
    handleEmbeddingProviderChange(event) {
      const index = Number(event.detail.value || 0)
      this.embeddingProviderIndex = index
      const selected = this.embeddingProviderOptions[index] || {}
      this.embForm.provider = selected.value || 'openai'
      if (!this.embForm.profileName || this.embForm.profileName === 'Embedding Profile') {
        this.embForm.profileName = selected.label || 'Embedding Profile'
      }
      if (!this.embForm.baseUrl) {
        this.embForm.baseUrl = selected.base_url || ''
      }
    },
    fillProviderDefaultUrl() {
      this.form.baseUrl = this.selectedProvider?.base_url || ''
    },
    fillEmbeddingDefaultUrl() {
      this.embForm.baseUrl = this.selectedEmbeddingProvider?.base_url || ''
    },
    buildCatalog() {
      const catalog = clone(this.catalogDraft || defaultCatalog())
      const services = catalog.services || {}
      if (!services.llm) {
        services.llm = { active_profile_id: null, active_model_id: null, profiles: [] }
      }
      if (!services.embedding) {
        services.embedding = { active_profile_id: null, active_model_id: null, profiles: [] }
      }
      if (!services.search) {
        services.search = { active_profile_id: null, profiles: [] }
      }
      catalog.services = services

      // LLM
      const profileId = services.llm.active_profile_id || 'llm-profile-1'
      const modelId = services.llm.active_model_id || 'llm-model-1'
      const modelValue = (this.form.modelId || '').trim()
      const modelName = (this.form.modelName || '').trim() || modelValue

      services.llm.active_profile_id = profileId
      services.llm.active_model_id = modelId
      services.llm.profiles = [
        {
          id: profileId,
          name: (this.form.profileName || '').trim() || this.selectedProvider?.label || 'LLM Profile',
          binding: this.form.provider || this.selectedProvider?.value || 'openai',
          base_url: (this.form.baseUrl || '').trim(),
          api_key: (this.form.apiKey || '').trim(),
          api_version: '',
          extra_headers: {},
          models: [
            {
              id: modelId,
              name: modelName,
              model: modelValue,
            },
          ],
        },
      ]

      // Embedding (only save if user filled in a model ID)
      const embModelValue = (this.embForm.modelId || '').trim()
      if (embModelValue) {
        const embProfileId = services.embedding.active_profile_id || 'emb-profile-1'
        const embModelId = services.embedding.active_model_id || 'emb-model-1'
        const embModelName = (this.embForm.modelName || '').trim() || embModelValue

        services.embedding.active_profile_id = embProfileId
        services.embedding.active_model_id = embModelId
        services.embedding.profiles = [
          {
            id: embProfileId,
            name: (this.embForm.profileName || '').trim() || this.selectedEmbeddingProvider?.label || 'Embedding Profile',
            binding: this.embForm.provider || this.selectedEmbeddingProvider?.value || 'openai',
            base_url: (this.embForm.baseUrl || '').trim(),
            api_key: (this.embForm.apiKey || '').trim(),
            api_version: '',
            extra_headers: {},
            models: [
              {
                id: embModelId,
                name: embModelName,
                model: embModelValue,
              },
            ],
          },
        ]
      }

      return catalog
    },
    async persistCatalog(showToast = true) {
      const catalog = this.buildCatalog()
      await this.settingsStore.updateCatalog(catalog)
      this.catalogDraft = clone(catalog)
      if (showToast) {
        uni.showToast({ title: 'Saved', icon: 'success' })
      }
      return catalog
    },
    async saveCatalog() {
      if (!this.form.modelId.trim()) {
        uni.showToast({ title: 'LLM Model ID is required', icon: 'none' })
        return
      }
      this.saving = true
      try {
        await this.persistCatalog(true)
      } catch (e) {
        uni.showToast({ title: e.message || 'Save failed', icon: 'none' })
      } finally {
        this.saving = false
      }
    },
    async applyCatalog() {
      if (!this.form.modelId.trim()) {
        uni.showToast({ title: 'LLM Model ID is required', icon: 'none' })
        return
      }
      this.applying = true
      try {
        const catalog = await this.persistCatalog(false)
        await this.settingsStore.applyCatalog(catalog)
        uni.showToast({ title: 'Applied', icon: 'success' })
      } catch (e) {
        uni.showToast({ title: e.message || 'Apply failed', icon: 'none' })
      } finally {
        this.applying = false
      }
    },
    async testConnection() {
      if (!this.form.modelId.trim()) {
        uni.showToast({ title: 'LLM Model ID is required', icon: 'none' })
        return
      }
      this.testing = true
      this.testResult = null
      try {
        const catalog = await this.persistCatalog(false)
        await this.settingsStore.applyCatalog(catalog)
        const result = await this.settingsStore.testLLMConnection()
        this.testResult = result
        uni.showToast({
          title: result.success ? 'LLM Connection OK' : 'LLM Connection failed',
          icon: 'none',
        })
      } catch (e) {
        this.testResult = {
          success: false,
          message: e.message || 'Connection failed',
          error: e.message || 'Connection failed',
        }
        uni.showToast({ title: e.message || 'Connection failed', icon: 'none' })
      } finally {
        this.testing = false
      }
    },
    async testEmbedding() {
      if (!this.embForm.modelId.trim()) {
        uni.showToast({ title: 'Embedding Model ID is required', icon: 'none' })
        return
      }
      this.testingEmb = true
      this.testResult = null
      try {
        const catalog = await this.persistCatalog(false)
        await this.settingsStore.applyCatalog(catalog)
        const result = await this.settingsStore.testEmbeddingConnection()
        this.testResult = result
        uni.showToast({
          title: result.success ? 'Embedding Connection OK' : 'Embedding Connection failed',
          icon: 'none',
        })
      } catch (e) {
        this.testResult = {
          success: false,
          message: e.message || 'Connection failed',
          error: e.message || 'Connection failed',
        }
        uni.showToast({ title: e.message || 'Connection failed', icon: 'none' })
      } finally {
        this.testingEmb = false
      }
    },
  },
}
</script>

<style lang="scss" scoped>
.llm-page {
  min-height: 100vh;
  padding: 30rpx;
  background: #f6f1eb;
}

.page-title {
  display: block;
  font-size: 42rpx;
  font-weight: 700;
  color: #2e221b;
}

.page-subtitle {
  display: block;
  margin-top: 12rpx;
  margin-bottom: 28rpx;
  font-size: 24rpx;
  line-height: 1.6;
  color: #8b735f;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 120rpx 0;
}

.panel {
  margin-bottom: 24rpx;
  padding: 28rpx;
  border-radius: 24rpx;
  background: #fffaf6;
  box-shadow: 0 12rpx 28rpx rgba(58, 38, 22, 0.08);
}

.section-title {
  display: block;
  margin-bottom: 20rpx;
  font-size: 30rpx;
  font-weight: 600;
  color: #2e221b;
}

.section-desc {
  display: block;
  margin-top: -12rpx;
  margin-bottom: 20rpx;
  font-size: 22rpx;
  color: #8b735f;
}

.field {
  margin-bottom: 22rpx;
}

.field:last-child {
  margin-bottom: 0;
}

.field-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.field-label {
  display: block;
  margin-bottom: 10rpx;
  font-size: 24rpx;
  color: #725846;
}

.field-tip {
  font-size: 22rpx;
  color: #c98b4a;
}

.text-input,
.picker-field {
  min-height: 84rpx;
  padding: 0 24rpx;
  border-radius: 18rpx;
  border: 1rpx solid #ead8c9;
  background: #ffffff;
  font-size: 28rpx;
  color: #2e221b;
  display: flex;
  align-items: center;
  box-sizing: border-box;
}

.picker-field {
  justify-content: space-between;
}

.action-row {
  display: flex;
  gap: 20rpx;
  margin-bottom: 20rpx;
}

.action-row.single {
  margin-bottom: 24rpx;
}

.action-btn {
  flex: 1;
}

.result-panel {
  background: #fff;
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.result-badge {
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  font-size: 22rpx;
}

.result-badge.ok {
  background: rgba(54, 179, 126, 0.12);
  color: #1f8f61;
}

.result-badge.fail {
  background: rgba(214, 79, 56, 0.12);
  color: #c14a32;
}

.result-line {
  display: block;
  margin-top: 10rpx;
  font-size: 25rpx;
  line-height: 1.6;
  color: #4a382b;
}

.result-error {
  display: block;
  margin-top: 12rpx;
  font-size: 24rpx;
  line-height: 1.6;
  color: #c14a32;
}
</style>
