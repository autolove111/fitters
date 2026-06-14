<template>
  <view class="container">
    <view class="score-card">
      <view class="score-left">
        <text class="score-label">今日健康指数</text>
        <view class="score-line">
          <text class="score-number">{{ dailyReport.score }}</text>
          <text class="score-unit">分</text>
        </view>
      </view>
      <view class="score-ring">
        <text class="ring-text">{{ dailyReport.score }}%</text>
      </view>
    </view>

    <view class="stats-grid">
      <view class="stat-card" @click="openHistory('workout')">
        <view class="stat-header">
          <text class="stat-icon">🏃</text>
          <text class="stat-title">今日运动</text>
        </view>
        <text class="stat-value">{{ todayStats.workoutMinutes }} / {{ todayStats.workoutTarget }} 分钟</text>
        <view class="progress-bar">
          <view class="progress-fill blue" :style="{ width: workoutPercent + '%' }"></view>
        </view>
      </view>

      <view class="stat-card" @click="openHistory('sleep')">
        <view class="stat-header">
          <text class="stat-icon">😴</text>
          <text class="stat-title">今日睡眠</text>
        </view>
        <text class="stat-value">{{ todayStats.sleepHours }} / {{ todayStats.sleepTarget }} 小时</text>
        <view class="progress-bar">
          <view class="progress-fill green" :style="{ width: sleepPercent + '%' }"></view>
        </view>
      </view>

      <view class="stat-card" @click="openHistory('diet')">
        <view class="stat-header">
          <text class="stat-icon">🍽️</text>
          <text class="stat-title">今日饮食</text>
        </view>
        <text class="stat-value">{{ todayStats.dietCalories }} / {{ todayStats.dietTarget }} 千卡</text>
        <view class="progress-bar">
          <view class="progress-fill amber" :style="{ width: dietPercent + '%' }"></view>
        </view>
      </view>

      <view class="stat-card" @click="openHistory('steps')">
        <view class="stat-header">
          <text class="stat-icon">👟</text>
          <text class="stat-title">今日步数</text>
        </view>
        <text class="stat-value">{{ todayStats.stepsCount }} / {{ todayStats.stepsTarget }} 步</text>
        <view class="progress-bar">
          <view class="progress-fill coral" :style="{ width: stepsPercent + '%' }"></view>
        </view>
      </view>
    </view>

    <view class="ai-plan-card">
      <view class="ai-hero">
        <view class="ai-mark">AI</view>
        <view class="ai-copy">
          <text class="ai-title">AI 私人健身顾问</text>
          <text class="ai-subtitle">根据你的运动、睡眠和饮食记录，安排今天更适合你的训练</text>
        </view>
        <button class="pro-link" @click="openProIntro">升级到 Pro</button>
      </view>

      <view class="tier-switch">
        <view class="tier-option" :class="{ active: membership.tier === 'FREE' }" @click="switchTier('FREE')">
          <text class="tier-kicker">Free</text>
          <text class="tier-name">今日建议</text>
          <text class="tier-meta">7天记录 · 简单计划</text>
        </view>
        <view class="tier-option pro" :class="{ active: membership.tier === 'PRO' }" @click="openProIntro">
          <text class="tier-kicker">Pro</text>
          <text class="tier-name">私人顾问</text>
          <text class="tier-meta">30天趋势 · 图表分析 · 权威依据</text>
        </view>
      </view>

      <view v-if="membership.tier !== 'PRO'" class="upgrade-strip" @click="openProIntro">
        <view class="upgrade-icon">✦</view>
        <view class="upgrade-copy">
          <text class="upgrade-title">升级到 Pro，解锁 AI 私人健身顾问</text>
          <text class="upgrade-text">看懂 30 天变化，生成图表分析，并给出更像真人教练的建议</text>
        </view>
        <text class="upgrade-action">了解</text>
      </view>

      <view class="ai-metrics">
        <view class="ai-metric">
          <text class="metric-value">{{ currentTierInfo.historyWindow }}</text>
          <text class="metric-label">看多长时间</text>
        </view>
        <view class="ai-metric">
          <text class="metric-value">{{ currentTierInfo.citationLimit }}</text>
          <text class="metric-label">参考来源</text>
        </view>
        <view class="ai-metric">
          <text class="metric-value">{{ remainingQuotaText }}</text>
          <text class="metric-label">今日次数</text>
        </view>
      </view>

      <button class="generate-ai-btn" @click="generateTrainingPlan" :disabled="generatingPlan">
        <text v-if="!generatingPlan">生成 AI 今日训练计划</text>
        <text v-else>AI 正在分析...</text>
      </button>

      <view v-if="planResult" class="plan-result">
        <view class="result-header">
          <text class="result-badge">{{ planResult.membershipTier || membership.tier }}</text>
          <text class="result-title">{{ localizeAiPlanText(planResult.title || '今日训练计划') }}</text>
        </view>
        <view class="rag-mode-card" :class="{ pro: planResult.knowledgeBaseMode === 'PERSONAL_RAG' }">
          <text class="rag-mode-title">{{ planResult.knowledgeBaseMode === 'PERSONAL_RAG' ? '专属RAG知识库' : '通用RAG知识库' }}</text>
          <text class="rag-mode-text">{{ planResult.knowledgeBaseLabel }}</text>
        </view>
        <view v-if="planResult.ragMetadata" class="rag-proof-card">
          <view class="rag-proof-head" @click="toggleRagDetails">
            <view>
              <text class="rag-proof-title">生成依据</text>
              <text class="rag-proof-copy">
                {{ planResult.ragMetadata.generationMode === 'LLM' ? 'AI 私人顾问已结合权威资料生成' : '当前使用兜底规则，训练建议仍可查看' }}
              </text>
            </view>
            <text class="rag-proof-badge" :class="{ fallback: planResult.ragMetadata.generationMode !== 'LLM' }">
              {{ planResult.ragMetadata.generationMode === 'LLM' ? 'AI生成' : '兜底生成' }}
            </text>
          </view>
          <view v-if="showRagDetails" class="rag-detail-grid">
            <view class="rag-detail-item">
              <text class="rag-detail-key">LLM</text>
              <text class="rag-detail-value">{{ planResult.ragMetadata.llmModel }}</text>
            </view>
            <view class="rag-detail-item">
              <text class="rag-detail-key">Embedding</text>
              <text class="rag-detail-value">{{ planResult.ragMetadata.embeddingModel }}</text>
            </view>
            <view class="rag-detail-item">
              <text class="rag-detail-key">召回</text>
              <text class="rag-detail-value">{{ planResult.ragMetadata.retrievedChunks }} 条</text>
            </view>
            <view class="rag-detail-item">
              <text class="rag-detail-key">重排序</text>
              <text class="rag-detail-value">{{ planResult.ragMetadata.rerankedChunks }} 条</text>
            </view>
            <view class="rag-detail-item">
              <text class="rag-detail-key">耗时</text>
              <text class="rag-detail-value">{{ planResult.ragMetadata.latencyMs }}ms</text>
            </view>
            <view v-if="planResult.ragMetadata.fallbackReason" class="rag-detail-item warn">
              <text class="rag-detail-key">原因</text>
              <text class="rag-detail-value">{{ planResult.ragMetadata.fallbackReason }}</text>
            </view>
          </view>
        </view>
        <text class="result-summary">{{ localizeAiPlanText(planResult.summary) }}</text>

        <view v-if="planResult.personalInsights && planResult.personalInsights.length" class="result-block">
          <text class="block-title">个人数据洞察</text>
          <text v-for="(item, index) in planResult.personalInsights" :key="'insight-' + index" class="block-line">{{ localizeAiPlanText(item) }}</text>
        </view>

        <view v-if="planResult.riskFlags && planResult.riskFlags.length" class="risk-panel">
          <text class="block-title">风险控制</text>
          <text v-for="(item, index) in planResult.riskFlags" :key="'risk-' + index" class="block-line">{{ localizeAiPlanText(item) }}</text>
        </view>

        <view v-if="planResult.items && planResult.items.length" class="workout-steps">
          <view v-for="(item, index) in planResult.items" :key="'step-' + index" class="step-card">
            <text class="step-index">{{ index + 1 }}</text>
            <view class="step-main">
              <text class="step-title">{{ localizePlanStage(item.stage) }} · {{ localizePlanActivity(item.activity) }}</text>
              <text class="step-meta">{{ item.minutes }} 分钟 / {{ localizePlanIntensity(item.intensity) }}</text>
              <text v-if="item.notes" class="step-note">{{ localizeAiPlanText(item.notes) }}</text>
            </view>
          </view>
        </view>

        <view v-if="realCitations.length" class="citation-row">
          <text v-for="(item, index) in realCitations" :key="'citation-' + index" class="citation-chip">{{ item.source }}</text>
        </view>

        <view v-if="planResult.trendAnalysis" class="coach-panel">
          <view class="coach-head">
            <text class="coach-title">Pro 私人顾问分析</text>
            <view class="coach-actions">
              <text class="coach-tag">{{ trendWindowText(planResult.trendAnalysis) }}</text>
              <button class="trend-detail-btn" @click="openTrendDetail">查看30天详情</button>
            </view>
          </view>
          <text class="coach-summary">{{ localizeAiPlanText(planResult.trendAnalysis.coachSummary) }}</text>
          <view class="coach-metrics">
            <view
              v-for="(item, index) in planResult.trendAnalysis.metrics"
              :key="'coach-metric-' + index"
              class="coach-metric"
              :class="item.tone"
            >
              <text class="coach-metric-value">{{ item.value }}</text>
              <text class="coach-metric-label">{{ item.label }}</text>
            </view>
          </view>
          <view class="trend-chart">
            <view v-for="(item, index) in trendPreviewItems(planResult.trendAnalysis.chart)" :key="'trend-' + index" class="trend-day">
              <view class="trend-bars">
                <view class="trend-bar workout" :style="{ height: workoutBarHeight(item.workoutMinutes) + '%' }"></view>
                <view class="trend-bar sleep" :style="{ height: sleepBarHeight(item.sleepHours) + '%' }"></view>
              </view>
              <text class="trend-label" :class="{ hidden: !isTrendPreviewLabel(index, planResult.trendAnalysis.chart) }">
                {{ shortTrendLabel(item.label) }}
              </text>
            </view>
          </view>
          <view class="chart-legend">
            <text class="legend-item workout-dot">运动</text>
            <text class="legend-item sleep-dot">睡眠</text>
          </view>
        </view>

        <view v-if="planResult.customizationBlocks && planResult.customizationBlocks.length" class="customization-panel">
          <text class="block-title">Pro 专属定制内容</text>
          <view
            v-for="(item, index) in planResult.customizationBlocks"
            :key="'custom-' + index"
            class="customization-card"
          >
            <text class="customization-title">{{ item.title }}</text>
            <text class="customization-text">{{ item.text }}</text>
          </view>
        </view>

        <view v-if="planResult.personalKnowledge && planResult.personalKnowledge.length" class="personal-rag-list">
          <text class="block-title">专属RAG命中的个人知识</text>
          <view v-for="(item, index) in planResult.personalKnowledge" :key="'personal-rag-' + index" class="personal-rag-card">
            <text class="personal-rag-source">{{ item.source }}</text>
            <text class="personal-rag-title">{{ item.title }}</text>
          </view>
        </view>

        <view v-if="realCitations.length" class="source-list">
          <text class="block-title">本次参考的权威来源</text>
          <view
            v-for="(item, index) in realCitations"
            :key="'source-' + index"
            class="source-card"
            @click="openAuthoritySource(item.url)"
          >
            <view>
              <text class="source-name">{{ item.source }}</text>
              <text class="source-title">{{ item.title }}</text>
              <text v-if="item.excerptChunk" class="source-excerpt">{{ item.excerptChunk }}</text>
            </view>
            <text class="source-open">{{ item.rerankScore ? Math.round(item.rerankScore * 100) + '%' : '查看' }}</text>
          </view>
        </view>

        <text v-if="planResult.upgradeHint" class="result-upgrade" @click="openProIntro">{{ localizeAiPlanText(planResult.upgradeHint) }}</text>
      </view>
    </view>

    <view class="action-buttons">
      <button class="action-btn primary" @click="navigateTo('workout/add')">＋ 运动</button>
      <button class="action-btn success" @click="navigateTo('sleep/add')">😴 睡眠</button>
      <button class="action-btn warning" @click="navigateTo('diet/add')">🍽️ 饮食</button>
    </view>

    <view v-if="showProModal" class="pro-modal-mask" @click="closeProIntro">
      <view class="pro-modal" @click.stop>
        <view class="pro-modal-head">
          <view class="pro-title-wrap">
            <text class="pro-modal-title">升级到 Fitters Pro</text>
            <text class="pro-modal-subtitle">把 AI 变成你的私人健身顾问，每天帮你看数据、避风险、安排训练</text>
          </view>
          <button class="modal-close" @click="closeProIntro">×</button>
        </view>
        <view class="vs-layout">
          <view class="vs-col free">
            <text class="vs-kicker">Free</text>
            <text class="vs-title">通用RAG知识库</text>
            <text class="vs-desc">像搜索公开健身资料：适合先体验，但不真正理解你。</text>
            <view class="vs-list">
              <text>通用人群训练建议</text>
              <text>只参考少量公共资料</text>
              <text>输出偏模板化</text>
              <text>不建立个人知识库</text>
            </view>
          </view>
          <view class="vs-badge">VS</view>
          <view class="vs-col pro">
            <text class="vs-kicker">Pro</text>
            <text class="vs-title">专属RAG知识库</text>
            <text class="vs-desc">在通用库之上，加入你的画像、30天记录、伤痛和器械偏好。</text>
            <view class="vs-list">
              <text>包含通用权威知识库</text>
              <text>新增个人画像RAG</text>
              <text>新增30天趋势RAG</text>
              <text>输出专属定制内容</text>
            </view>
          </view>
        </view>
        <view class="pro-selling-points">
          <view class="selling-card highlight">
            <text class="selling-number">通用库+</text>
            <text class="selling-label">权威资料全包含</text>
          </view>
          <view class="selling-card">
            <text class="selling-number">个人库</text>
            <text class="selling-label">画像/历史/风险</text>
          </view>
          <view class="selling-card">
            <text class="selling-number">定制输出</text>
            <text class="selling-label">个性化私人定制</text>
          </view>
        </view>
        <view class="authority-panel">
          <text class="authority-title">Pro 的专属RAG包含这些通用权威来源</text>
          <view
            v-for="item in authoritySources"
            :key="item.url"
            class="authority-row"
            @click="openAuthoritySource(item.url)"
          >
            <text class="authority-name">{{ item.source }}</text>
            <text class="authority-text">{{ item.title }}</text>
          </view>
        </view>
        <button class="activate-pro-btn" @click="activatePro">立即体验 Pro</button>
      </view>
    </view>

    <view v-if="loading" class="loading-mask">
      <view class="loading-content">加载中...</view>
    </view>
  </view>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useUserStore } from '@/store/user'
import { fitnessProfileApi, membershipApi, statsApi } from '@/utils/api'
import {
  getPlanTierPresentation,
  getRealRagCitations,
  localizeAiPlanText,
  localizePlanActivity,
  localizePlanIntensity,
  localizePlanStage
} from '@/utils/aiPlanFormatter.mjs'

const userStore = useUserStore()
const { isLoggedIn } = userStore

const loading = ref(false)
const generatingPlan = ref(false)
const showProModal = ref(false)
const showRagDetails = ref(false)
const planResult = ref(null)
const membership = ref({ tier: 'FREE', dailyAiQuota: 3, remainingAiQuota: 3 })
const fitnessProfile = ref({
  goal: 'fat_loss',
  fitnessLevel: 'beginner',
  injuries: 'knee discomfort',
  equipment: ['yoga mat', 'resistance band'],
  preferredWorkoutTime: 'evening'
})

const todayStats = ref({
  workoutMinutes: 0,
  workoutTarget: 30,
  sleepHours: 0,
  sleepTarget: 8,
  dietCalories: 0,
  dietTarget: 2000,
  stepsCount: 0,
  stepsTarget: 10000
})
const dailyReport = ref({ score: 0 })
const authoritySources = [
  {
    source: 'WHO',
    title: '成年人身体活动建议',
    url: 'https://www.who.int/publications/i/item/9789240015128'
  },
  {
    source: 'CDC',
    title: '有氧 + 力量训练建议',
    url: 'https://www.cdc.gov/physical-activity-basics/guidelines/adults.html'
  },
  {
    source: 'ACSM',
    title: '运动强度与筛查指南',
    url: 'https://acsm.org/education-resources/trending-topics-resources/physical-activity-guidelines/'
  },
  {
    source: 'Mayo Clinic',
    title: '如何判断运动强度',
    url: 'https://www.mayoclinic.org/healthy-lifestyle/fitness/in-depth/exercise-intensity/art-20046887'
  }
]

const workoutPercent = computed(() => percent(todayStats.value.workoutMinutes, todayStats.value.workoutTarget))
const sleepPercent = computed(() => percent(todayStats.value.sleepHours, todayStats.value.sleepTarget))
const dietPercent = computed(() => percent(todayStats.value.dietCalories, todayStats.value.dietTarget))
const stepsPercent = computed(() => percent(todayStats.value.stepsCount, todayStats.value.stepsTarget))
const currentTierInfo = computed(() => getPlanTierPresentation(membership.value.tier))
const realCitations = computed(() => getRealRagCitations(planResult.value))
const remainingQuotaText = computed(() => {
  const remaining = membership.value.remainingAiQuota ?? Math.max(0, (membership.value.dailyAiQuota || 0) - (membership.value.usedAiQuota || 0))
  return `${remaining}/${membership.value.dailyAiQuota || 3}`
})

function percent(value, target) {
  return Math.min(100, Math.round(target > 0 ? (value / target) * 100 : 0))
}

function workoutBarHeight(value) {
  return Math.max(12, Math.min(100, Math.round((Number(value) || 0) / 60 * 100)))
}

function sleepBarHeight(value) {
  return Math.max(12, Math.min(100, Math.round((Number(value) || 0) / 9 * 100)))
}

function trendPreviewItems(chart) {
  return Array.isArray(chart) ? chart.slice(-10) : []
}

function isTrendPreviewLabel(index, chart) {
  const previewLength = trendPreviewItems(chart).length
  return index % 2 === 0 || index === previewLength - 1
}

function shortTrendLabel(label = '') {
  const value = String(label || '')
  const match = value.match(/^0?(\d{1,2})-0?(\d{1,2})$/)
  if (match) return `${Number(match[1])}/${Number(match[2])}`
  return value.replace('-', '/')
}

function trendWindowText(analysis) {
  const days = analysis?.windowDays || analysis?.chart?.length || 0
  return days ? `${days}天趋势` : '趋势分析'
}

function toggleRagDetails() {
  showRagDetails.value = !showRagDetails.value
}

function openTrendDetail() {
  const analysis = planResult.value?.trendAnalysis
  if (!analysis) {
    uni.showToast({ title: '请先生成 Pro 计划', icon: 'none' })
    return
  }
  uni.setStorageSync('ai_trend_analysis', analysis)
  uni.navigateTo({ url: '/pages/workout/ai-trend' })
}

function openAuthoritySource(url) {
  if (!url) return
  if (typeof window !== 'undefined' && window.open) {
    window.open(url, '_blank')
    return
  }
  uni.setClipboardData({
    data: url,
    success: () => uni.showToast({ title: '链接已复制', icon: 'none' })
  })
}

async function loadDashboard() {
  if (!isLoggedIn.value) return
  loading.value = true
  try {
    const [todayData, sleepTodayData, dietTodayData, memberData, profileData] = await Promise.all([
      statsApi.today(),
      statsApi.sleepToday(),
      statsApi.dietToday(),
      membershipApi.get(),
      fitnessProfileApi.get()
    ])

    const workoutTarget = todayData.targetMinutes ?? 30
    const workoutMinutes = todayData.completedMinutes ?? 0
    const sleepTarget = sleepTodayData.targetHours ?? 8
    const sleepHours = Array.isArray(sleepTodayData.records)
      ? sleepTodayData.records.reduce((sum, item) => sum + (item.durationHours || 0), 0)
      : 0
    const dietTarget = dietTodayData.targetCalories ?? 2000
    const dietCalories = dietTodayData.totalCalories ?? 0
    const stepsTarget = todayData.stepsTarget ?? 10000
    const stepsCount = todayData.steps ?? 0

    todayStats.value = { workoutMinutes, workoutTarget, sleepHours, sleepTarget, dietCalories, dietTarget, stepsCount, stepsTarget }
    membership.value = { ...membership.value, ...memberData }
    fitnessProfile.value = { ...fitnessProfile.value, ...profileData }
    updateHealthScore()
  } catch (error) {
    uni.showToast({ title: error.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function updateHealthScore() {
  const workoutScore = percent(todayStats.value.workoutMinutes, todayStats.value.workoutTarget)
  const sleepScore = percent(todayStats.value.sleepHours, todayStats.value.sleepTarget)
  const dietTarget = todayStats.value.dietTarget
  const dietScore = dietTarget > 0 ? Math.max(0, 100 - Math.abs(todayStats.value.dietCalories - dietTarget) / dietTarget * 100) : 0
  const stepsScore = percent(todayStats.value.stepsCount, todayStats.value.stepsTarget)
  dailyReport.value.score = Math.round((workoutScore + sleepScore + dietScore + stepsScore) / 4)
}

async function switchTier(tier) {
  if (tier === 'PRO') {
    openProIntro()
    return
  }
  try {
    membership.value = { ...membership.value, ...(await membershipApi.setMockTier('FREE')) }
    planResult.value = null
  } catch (error) {
    uni.showToast({ title: error.message || '切换失败', icon: 'none' })
  }
}

function openProIntro() {
  showProModal.value = true
}

function closeProIntro() {
  showProModal.value = false
}

async function activatePro() {
  try {
    membership.value = { ...membership.value, ...(await membershipApi.setMockTier('PRO')) }
    showProModal.value = false
    planResult.value = null
    uni.showToast({ title: 'Pro 已开启', icon: 'success' })
  } catch (error) {
    uni.showToast({ title: error.message || '开启失败', icon: 'none' })
  }
}

async function generateTrainingPlan() {
  if (generatingPlan.value) return
  generatingPlan.value = true
  planResult.value = null
  try {
    const profile = fitnessProfile.value
    const result = await statsApi.generatePersonalizedPlan({
      requestedDays: membership.value.tier === 'PRO' ? 30 : 7,
      goal: profile.goal || 'fat_loss',
      injuries: profile.injuries || '',
      equipment: profile.equipment || [],
      preferredTime: profile.preferredWorkoutTime || 'evening',
      question: 'Generate a safe, personalized plan for today.'
    })
    planResult.value = result
    if (result.membership) {
      membership.value = { ...membership.value, ...result.membership }
    }
  } catch (error) {
    uni.showToast({ title: error.message || '生成失败', icon: 'none' })
  } finally {
    generatingPlan.value = false
  }
}

function openHistory(metric) {
  uni.navigateTo({ url: `/pages/workout/history?metric=${metric}` })
}

function navigateTo(page) {
  uni.navigateTo({ url: `/pages/${page}` })
}

onMounted(() => {
  if (!isLoggedIn.value) {
    uni.reLaunch({ url: '/pages/index/index' })
    return
  }
  loadDashboard()
})
</script>

<style scoped>
.container {
  min-height: 100vh;
  padding: 30rpx;
  padding-bottom: 100rpx;
  background: #f5f7fa;
}

.score-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 40rpx;
  margin-bottom: 24rpx;
  color: #fff;
  background: linear-gradient(135deg, #409eff 0%, #256fd8 100%);
  border-radius: 24rpx;
  box-shadow: 0 18rpx 40rpx rgba(45, 117, 216, 0.24);
}
.score-label {
  display: block;
  font-size: 28rpx;
  opacity: 0.92;
}
.score-line {
  display: flex;
  align-items: baseline;
}
.score-number {
  font-size: 78rpx;
  font-weight: 800;
  line-height: 1;
}
.score-unit {
  margin-left: 8rpx;
  font-size: 30rpx;
}
.score-ring {
  width: 118rpx;
  height: 118rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.92);
}
.ring-text {
  color: #2b75dc;
  font-size: 30rpx;
  font-weight: 800;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18rpx;
  margin-bottom: 26rpx;
}
.stat-card {
  background: #fff;
  border-radius: 18rpx;
  padding: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(19, 35, 54, 0.06);
}
.stat-header {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 14rpx;
}
.stat-title {
  color: #536171;
  font-size: 28rpx;
}
.stat-value {
  display: block;
  color: #1f2933;
  font-size: 28rpx;
  margin-bottom: 18rpx;
}
.progress-bar {
  height: 8rpx;
  border-radius: 10rpx;
  overflow: hidden;
  background: #e6ebf0;
}
.progress-fill {
  height: 100%;
}
.blue { background: #409eff; }
.green { background: #59c23a; }
.amber { background: #eda932; }
.coral { background: #f56c6c; }

.ai-plan-card {
  margin-bottom: 26rpx;
  padding: 28rpx;
  border-radius: 26rpx;
  background: linear-gradient(180deg, #122f2b 0%, #1f7a5c 100%);
  box-shadow: 0 18rpx 42rpx rgba(25, 108, 83, 0.25);
}
.ai-hero {
  display: flex;
  align-items: center;
  gap: 18rpx;
  margin-bottom: 24rpx;
}
.ai-mark {
  width: 76rpx;
  height: 76rpx;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #d6f7a3;
  color: #12382f;
  font-size: 30rpx;
  font-weight: 900;
}
.ai-copy {
  flex: 1;
  min-width: 0;
}
.ai-title {
  display: block;
  color: #fff;
  font-size: 34rpx;
  font-weight: 800;
  margin-bottom: 8rpx;
}
.ai-subtitle {
  display: block;
  color: rgba(255, 255, 255, 0.78);
  font-size: 24rpx;
  line-height: 1.35;
}
.pro-link {
  min-width: 136rpx;
  height: 60rpx;
  line-height: 60rpx;
  padding: 0 22rpx;
  color: #12382f;
  background: #fff;
  border: none;
  border-radius: 999rpx;
  font-size: 24rpx;
  font-weight: 800;
}

.tier-switch {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
  margin-bottom: 18rpx;
}
.tier-option {
  padding: 22rpx;
  border-radius: 18rpx;
  background: rgba(255, 255, 255, 0.12);
  border: 2rpx solid rgba(255, 255, 255, 0.16);
}
.tier-option.active {
  background: #fff;
  border-color: #d6f7a3;
}
.tier-option.pro {
  background: rgba(214, 247, 163, 0.16);
}
.tier-option.pro.active {
  background: linear-gradient(135deg, #fff 0%, #ecffd0 100%);
}
.tier-kicker,
.tier-name,
.tier-meta {
  display: block;
}
.tier-kicker {
  color: #d6f7a3;
  font-size: 22rpx;
  font-weight: 900;
  letter-spacing: 1rpx;
}
.tier-option.active .tier-kicker,
.tier-option.active .tier-name,
.tier-option.active .tier-meta {
  color: #12382f;
}
.tier-name {
  color: #fff;
  font-size: 30rpx;
  font-weight: 800;
  margin: 8rpx 0;
}
.tier-meta {
  color: rgba(255, 255, 255, 0.7);
  font-size: 23rpx;
}

.upgrade-strip {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 18rpx;
  margin-bottom: 18rpx;
  border-radius: 18rpx;
  background: rgba(255, 255, 255, 0.14);
  border: 1rpx solid rgba(214, 247, 163, 0.35);
}
.upgrade-icon {
  width: 54rpx;
  height: 54rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #12382f;
  background: #d6f7a3;
  font-size: 28rpx;
}
.upgrade-copy {
  flex: 1;
}
.upgrade-title,
.upgrade-text {
  display: block;
}
.upgrade-title {
  color: #fff;
  font-size: 26rpx;
  font-weight: 800;
}
.upgrade-text {
  color: rgba(255, 255, 255, 0.72);
  font-size: 22rpx;
  margin-top: 4rpx;
}
.upgrade-action {
  color: #d6f7a3;
  font-size: 24rpx;
  font-weight: 800;
}

.ai-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
  margin-bottom: 20rpx;
}
.ai-metric {
  padding: 16rpx 10rpx;
  border-radius: 16rpx;
  text-align: center;
  background: rgba(255, 255, 255, 0.12);
}
.metric-value {
  display: block;
  color: #fff;
  font-size: 23rpx;
  font-weight: 800;
}
.metric-label {
  display: block;
  color: rgba(255, 255, 255, 0.68);
  font-size: 20rpx;
  margin-top: 6rpx;
}
.generate-ai-btn {
  height: 88rpx;
  line-height: 88rpx;
  color: #12382f;
  background: #d6f7a3;
  border-radius: 18rpx;
  font-size: 30rpx;
  font-weight: 900;
}
.generate-ai-btn[disabled] {
  opacity: 0.72;
}

.plan-result {
  margin-top: 22rpx;
  padding: 24rpx;
  border-radius: 20rpx;
  background: #fff;
}
.result-header {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 12rpx;
}
.result-badge {
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
  color: #fff;
  background: #1f7a5c;
  font-size: 20rpx;
  font-weight: 900;
}
.result-title {
  flex: 1;
  color: #1f2933;
  font-size: 30rpx;
  font-weight: 800;
}
.result-summary {
  display: block;
  color: #43515f;
  font-size: 26rpx;
  line-height: 1.5;
}
.rag-mode-card {
  padding: 16rpx 18rpx;
  margin-bottom: 14rpx;
  border-radius: 16rpx;
  background: #f1f5f9;
  border: 1rpx solid #e2e8f0;
}
.rag-mode-card.pro {
  background: #efffde;
  border-color: #d6f7a3;
}
.rag-mode-title,
.rag-mode-text {
  display: block;
}
.rag-mode-title {
  color: #12382f;
  font-size: 24rpx;
  font-weight: 900;
}
.rag-mode-text {
  color: #536171;
  font-size: 22rpx;
  line-height: 1.35;
  margin-top: 4rpx;
}
.rag-proof-card {
  margin-bottom: 14rpx;
  padding: 18rpx;
  border-radius: 16rpx;
  background: linear-gradient(135deg, #f7fff0 0%, #eefaf5 100%);
  border: 1rpx solid #d8f6b2;
}
.rag-proof-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}
.rag-proof-title,
.rag-proof-copy {
  display: block;
}
.rag-proof-title {
  color: #12382f;
  font-size: 24rpx;
  font-weight: 900;
}
.rag-proof-copy {
  color: #536171;
  font-size: 22rpx;
  line-height: 1.35;
  margin-top: 4rpx;
}
.rag-proof-badge {
  flex-shrink: 0;
  padding: 8rpx 14rpx;
  border-radius: 999rpx;
  color: #0d3b31;
  background: #d6f7a3;
  font-size: 21rpx;
  font-weight: 900;
}
.rag-proof-badge.fallback {
  color: #8a4b08;
  background: #fff0cf;
}
.rag-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10rpx;
  margin-top: 14rpx;
}
.rag-detail-item {
  min-width: 0;
  padding: 12rpx;
  border-radius: 12rpx;
  background: rgba(255, 255, 255, 0.76);
}
.rag-detail-item.warn {
  grid-column: 1 / -1;
  background: #fff7ed;
}
.rag-detail-key,
.rag-detail-value {
  display: block;
}
.rag-detail-key {
  color: #6b7a86;
  font-size: 19rpx;
}
.rag-detail-value {
  color: #12382f;
  font-size: 22rpx;
  font-weight: 800;
  margin-top: 4rpx;
  word-break: break-word;
}
.result-block,
.risk-panel,
.workout-steps {
  margin-top: 18rpx;
}
.risk-panel {
  padding: 18rpx;
  border-radius: 16rpx;
  background: #fff7ed;
}
.block-title {
  display: block;
  color: #1f2933;
  font-size: 26rpx;
  font-weight: 800;
  margin-bottom: 10rpx;
}
.block-line {
  display: block;
  color: #536171;
  font-size: 24rpx;
  line-height: 1.45;
  margin-bottom: 6rpx;
}
.step-card {
  display: flex;
  gap: 16rpx;
  padding: 18rpx 0;
  border-top: 1rpx solid #edf1f5;
}
.step-index {
  width: 44rpx;
  height: 44rpx;
  line-height: 44rpx;
  text-align: center;
  border-radius: 50%;
  color: #fff;
  background: #1f7a5c;
  font-size: 22rpx;
  font-weight: 900;
}
.step-main {
  flex: 1;
}
.step-title,
.step-meta,
.step-note {
  display: block;
}
.step-title {
  color: #1f2933;
  font-size: 25rpx;
  font-weight: 800;
}
.step-meta {
  color: #1f7a5c;
  font-size: 23rpx;
  margin-top: 4rpx;
}
.step-note {
  color: #657280;
  font-size: 23rpx;
  line-height: 1.4;
  margin-top: 6rpx;
}
.citation-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 18rpx;
}
.citation-chip {
  padding: 8rpx 14rpx;
  border-radius: 999rpx;
  color: #1f7a5c;
  background: #e9f7f1;
  font-size: 22rpx;
  font-weight: 800;
}
.coach-panel {
  margin-top: 20rpx;
  padding: 22rpx;
  border-radius: 20rpx;
  background: linear-gradient(180deg, #f0ffe0 0%, #ffffff 100%);
  border: 1rpx solid #d8f6b2;
}
.coach-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 12rpx;
}
.coach-title {
  color: #12382f;
  font-size: 28rpx;
  font-weight: 900;
}
.coach-actions {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-shrink: 0;
}
.coach-tag {
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
  color: #12382f;
  background: #d6f7a3;
  font-size: 20rpx;
  font-weight: 900;
}
.trend-detail-btn {
  height: 52rpx;
  line-height: 52rpx;
  margin: 0;
  padding: 0 18rpx;
  border-radius: 999rpx;
  color: #ffffff;
  background: #1f7a5c;
  font-size: 21rpx;
  font-weight: 900;
  box-shadow: 0 8rpx 18rpx rgba(31, 122, 92, 0.18);
}
.trend-detail-btn::after {
  border: none;
}
.coach-summary {
  display: block;
  color: #425466;
  font-size: 24rpx;
  line-height: 1.45;
}
.coach-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10rpx;
  margin-top: 18rpx;
}
.coach-metric {
  padding: 14rpx 8rpx;
  border-radius: 14rpx;
  text-align: center;
  background: #eef7f3;
}
.coach-metric.warn {
  background: #fff4df;
}
.coach-metric-value,
.coach-metric-label {
  display: block;
}
.coach-metric-value {
  color: #12382f;
  font-size: 22rpx;
  font-weight: 900;
}
.coach-metric-label {
  color: #657280;
  font-size: 19rpx;
  margin-top: 4rpx;
}
.trend-chart {
  min-height: 178rpx;
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 10rpx;
  margin-top: 22rpx;
  padding: 18rpx 16rpx 10rpx;
  border-radius: 16rpx;
  background:
    linear-gradient(180deg, rgba(31, 122, 92, 0.06), rgba(31, 122, 92, 0)),
    #f7faf8;
  overflow: hidden;
}
.trend-day {
  flex: 1 1 0;
  min-width: 0;
  height: 150rpx;
  display: grid;
  grid-template-rows: 122rpx 24rpx;
  row-gap: 6rpx;
  align-items: center;
}
.trend-bars {
  height: 122rpx;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 6rpx;
}
.trend-bar {
  width: 10rpx;
  min-height: 12rpx;
  border-radius: 999rpx 999rpx 0 0;
}
.trend-bar.workout {
  background: #1f7a5c;
}
.trend-bar.sleep {
  background: #5ba7ff;
}
.trend-label {
  width: 100%;
  height: 24rpx;
  line-height: 24rpx;
  color: #7a8794;
  font-size: 18rpx;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
}
.trend-label.hidden {
  visibility: hidden;
}
.chart-legend {
  display: flex;
  justify-content: center;
  gap: 28rpx;
  margin-top: 12rpx;
}
.legend-item {
  color: #536171;
  font-size: 21rpx;
}
.workout-dot::before,
.sleep-dot::before {
  content: '';
  display: inline-block;
  width: 14rpx;
  height: 14rpx;
  margin-right: 8rpx;
  border-radius: 50%;
}
.workout-dot::before {
  background: #1f7a5c;
}
.sleep-dot::before {
  background: #5ba7ff;
}
.source-list {
  margin-top: 20rpx;
}
.source-card {
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
  padding: 16rpx 0;
  border-top: 1rpx solid #edf1f5;
}
.source-name,
.source-title {
  display: block;
}
.source-name {
  color: #1f7a5c;
  font-size: 22rpx;
  font-weight: 900;
}
.source-title {
  color: #536171;
  font-size: 22rpx;
  line-height: 1.35;
  margin-top: 4rpx;
}
.source-excerpt {
  display: block;
  color: #7a8794;
  font-size: 20rpx;
  line-height: 1.35;
  margin-top: 6rpx;
}
.source-open {
  align-self: center;
  color: #1f7a5c;
  font-size: 22rpx;
  font-weight: 800;
}
.customization-panel,
.personal-rag-list {
  margin-top: 20rpx;
}
.customization-card,
.personal-rag-card {
  padding: 16rpx;
  margin-top: 10rpx;
  border-radius: 16rpx;
  background: #f7faf8;
  border: 1rpx solid #edf1f5;
}
.customization-title,
.customization-text,
.personal-rag-source,
.personal-rag-title {
  display: block;
}
.customization-title,
.personal-rag-source {
  color: #1f7a5c;
  font-size: 23rpx;
  font-weight: 900;
}
.customization-text,
.personal-rag-title {
  color: #536171;
  font-size: 22rpx;
  line-height: 1.4;
  margin-top: 6rpx;
}
.result-upgrade {
  display: block;
  margin-top: 18rpx;
  color: #1f7a5c;
  font-size: 24rpx;
  font-weight: 800;
}

.action-buttons {
  display: flex;
  gap: 18rpx;
  margin-bottom: 28rpx;
}
.action-btn {
  flex: 1;
  height: 88rpx;
  line-height: 88rpx;
  border: none;
  border-radius: 44rpx;
  color: #fff;
  font-size: 30rpx;
  font-weight: 700;
}
.primary { background: linear-gradient(135deg, #409eff, #2c6ed1); }
.success { background: #59c23a; }
.warning { background: #eda932; }

.pro-modal-mask,
.loading-mask {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  background: rgba(10, 22, 30, 0.48);
}
.pro-modal {
  width: 86vw;
  max-width: 680rpx;
  padding: 30rpx;
  border-radius: 28rpx;
  background:
    radial-gradient(circle at 92% 4%, rgba(180, 238, 111, 0.36), transparent 26%),
    linear-gradient(180deg, #ffffff 0%, #f2faf4 100%);
  border: 1rpx solid rgba(31, 122, 92, 0.12);
  box-shadow: 0 30rpx 80rpx rgba(16, 48, 40, 0.24);
}
.pro-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 22rpx;
}
.pro-title-wrap {
  flex: 1;
}
.pro-modal-title {
  display: block;
  color: #0d3b31;
  font-size: 36rpx;
  font-weight: 900;
}
.pro-modal-subtitle {
  display: block;
  color: #5b6f68;
  font-size: 24rpx;
  line-height: 1.4;
  margin-top: 8rpx;
}
.modal-close {
  width: 56rpx;
  height: 56rpx;
  line-height: 56rpx;
  padding: 0;
  color: #31564c;
  background: rgba(13, 59, 49, 0.08);
  border-radius: 50%;
  font-size: 34rpx;
}
.compare-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14rpx;
  margin-bottom: 24rpx;
}
.vs-layout {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
  margin-bottom: 18rpx;
}
.vs-col {
  min-height: 280rpx;
  padding: 22rpx;
  border-radius: 20rpx;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(241, 249, 244, 0.92)),
    #f4faf6;
  border: 1rpx solid rgba(31, 122, 92, 0.1);
  box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.9);
}
.vs-col.pro {
  color: #fff;
  background:
    radial-gradient(circle at 90% 0%, rgba(185, 245, 119, 0.3), transparent 34%),
    linear-gradient(145deg, #0b3b31 0%, #11614d 54%, #20946b 100%);
  border-color: rgba(198, 248, 143, 0.28);
  box-shadow: 0 18rpx 40rpx rgba(17, 97, 77, 0.3);
}
.vs-badge {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 58rpx;
  height: 58rpx;
  line-height: 58rpx;
  margin-left: -29rpx;
  margin-top: -29rpx;
  text-align: center;
  border-radius: 50%;
  color: #0d3b31;
  background: linear-gradient(135deg, #e8ffd0 0%, #b7ed65 100%);
  font-size: 22rpx;
  font-weight: 900;
  border: 4rpx solid rgba(255, 255, 255, 0.72);
  box-shadow: 0 10rpx 24rpx rgba(36, 132, 91, 0.28);
  z-index: 2;
}
.vs-kicker,
.vs-title,
.vs-desc,
.vs-list text {
  display: block;
}
.vs-kicker {
  color: #0f7f60;
  font-size: 22rpx;
  font-weight: 900;
}
.vs-title {
  color: #0d3b31;
  font-size: 30rpx;
  font-weight: 900;
  margin-top: 6rpx;
}
.vs-desc {
  color: #5b6f68;
  font-size: 22rpx;
  line-height: 1.35;
  margin-top: 10rpx;
}
.vs-list {
  margin-top: 14rpx;
}
.vs-list text {
  color: #405a52;
  font-size: 21rpx;
  line-height: 1.5;
}
.vs-list text::before {
  content: '•';
  margin-right: 8rpx;
}
.vs-col.pro .vs-kicker,
.vs-col.pro .vs-title,
.vs-col.pro .vs-desc,
.vs-col.pro .vs-list text {
  color: #fff;
}
.vs-col.pro .vs-desc,
.vs-col.pro .vs-list text {
  opacity: 0.9;
}
.pro-selling-points {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
  margin-bottom: 18rpx;
}
.selling-card {
  padding: 18rpx 10rpx;
  border-radius: 18rpx;
  text-align: center;
  background: linear-gradient(180deg, #ffffff 0%, #edf8f1 100%);
  border: 1rpx solid rgba(31, 122, 92, 0.1);
  box-shadow: 0 8rpx 22rpx rgba(31, 122, 92, 0.06);
}
.selling-card.highlight {
  background: linear-gradient(135deg, #eaffce 0%, #c9f47f 100%);
  border-color: rgba(70, 154, 81, 0.18);
}
.selling-number,
.selling-label {
  display: block;
}
.selling-number {
  color: #0d3b31;
  font-size: 30rpx;
  font-weight: 900;
}
.selling-label {
  color: #60736d;
  font-size: 21rpx;
  margin-top: 6rpx;
}
.compare-col {
  padding: 22rpx;
  border-radius: 20rpx;
  background: #f6f8fa;
}
.compare-col.pro {
  background: linear-gradient(135deg, #12382f 0%, #1f7a5c 100%);
}
.compare-title,
.compare-line {
  display: block;
}
.compare-title {
  color: #1f2933;
  font-size: 30rpx;
  font-weight: 900;
  margin-bottom: 12rpx;
}
.compare-line {
  color: #536171;
  font-size: 23rpx;
  line-height: 1.5;
}
.compare-line.muted {
  color: #94a3b8;
}
.compare-col.pro .compare-title,
.compare-col.pro .compare-line {
  color: #fff;
}
.authority-panel {
  padding: 18rpx;
  margin-bottom: 22rpx;
  border-radius: 18rpx;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(239, 248, 243, 0.92)),
    #f5fbf7;
  border: 1rpx solid rgba(31, 122, 92, 0.1);
}
.authority-title {
  display: block;
  color: #0d3b31;
  font-size: 25rpx;
  font-weight: 900;
  margin-bottom: 10rpx;
}
.authority-row {
  display: flex;
  gap: 12rpx;
  padding: 10rpx 0;
  border-top: 1rpx solid rgba(31, 122, 92, 0.12);
}
.authority-row:first-of-type {
  border-top: none;
}
.authority-name {
  width: 150rpx;
  color: #0f7f60;
  font-size: 22rpx;
  font-weight: 900;
}
.authority-text {
  flex: 1;
  color: #5b6f68;
  font-size: 22rpx;
  line-height: 1.35;
}
.activate-pro-btn {
  height: 82rpx;
  line-height: 82rpx;
  color: #0d3b31;
  background: linear-gradient(135deg, #dcff9c 0%, #a9e855 45%, #6fd37b 100%);
  border-radius: 18rpx;
  font-size: 30rpx;
  font-weight: 900;
  box-shadow: 0 14rpx 30rpx rgba(99, 193, 89, 0.28);
}
.activate-pro-btn::after {
  border: none;
}
.loading-content {
  padding: 30rpx 60rpx;
  border-radius: 18rpx;
  background: #fff;
  color: #1f2933;
  font-size: 28rpx;
}
</style>
