export function formatAiPlanForDisplay(plan) {
  if (!plan) return ''

  const lines = []
  const tier = plan.membershipTier || plan.membership?.tier || 'FREE'
  lines.push(`[${tier}] ${plan.summary || plan.title || 'AI plan generated.'}`)

  if (Array.isArray(plan.personalInsights) && plan.personalInsights.length) {
    lines.push('', 'Personal insights:')
    plan.personalInsights.forEach((item, index) => lines.push(`${index + 1}. ${item}`))
  }

  if (Array.isArray(plan.riskFlags) && plan.riskFlags.length) {
    lines.push('', 'Risk controls:')
    plan.riskFlags.forEach((item, index) => lines.push(`${index + 1}. ${item}`))
  }

  if (Array.isArray(plan.items) && plan.items.length) {
    lines.push('', 'Workout steps:')
    plan.items.forEach((item, index) => {
      lines.push(`${index + 1}. ${item.stage}: ${item.activity} ${item.minutes} min (${item.intensity})`)
      if (item.notes) lines.push(`   ${item.notes}`)
    })
  }

  if (Array.isArray(plan.citations) && plan.citations.length) {
    lines.push('', 'RAG citations:')
    plan.citations.forEach((item, index) => {
      lines.push(`${index + 1}. ${item.source} - ${item.title || item.url || 'guidance'}`)
    })
  }

  if (plan.upgradeHint) {
    lines.push('', `Upgrade: ${plan.upgradeHint}`)
  }

  return lines.join('\n')
}

export function getRealRagCitations(plan) {
  const metadataCitations = plan?.ragMetadata?.citations
  if (Array.isArray(metadataCitations) && metadataCitations.length) {
    return metadataCitations
  }
  return Array.isArray(plan?.citations) ? plan.citations : []
}

const GOAL_LABELS = {
  fat_loss: '减脂',
  muscle_gain: '增肌',
  endurance: '提升耐力',
  general_fitness: '综合健康'
}

const EQUIPMENT_LABELS = {
  'yoga mat': '瑜伽垫',
  'resistance band': '弹力带',
  bodyweight: '徒手'
}

export function localizePlanStage(stage = '') {
  const labels = {
    'Warm-up': '热身激活',
    'Main training': '主训练',
    'Cool-down': '放松恢复'
  }
  return labels[stage] || stage
}

export function localizePlanIntensity(intensity = '') {
  const labels = {
    low: '低强度',
    moderate: '中等强度',
    'low-to-moderate': '低到中等强度'
  }
  return labels[intensity] || intensity
}

export function localizePlanActivity(activity = '') {
  if (!activity) return ''
  if (activity === 'Joint mobility and easy walk') return '关节活动 + 轻松步行'
  if (activity === 'Stretching and breathing reset') return '拉伸 + 呼吸调整'

  let localized = activity
  Object.entries(EQUIPMENT_LABELS).forEach(([source, label]) => {
    localized = localized.replaceAll(source, label)
  })
  Object.entries(GOAL_LABELS).forEach(([source, label]) => {
    localized = localized.replaceAll(source, label)
  })
  return localized.replace('circuit for', '循环训练：')
}

export function localizeAiPlanText(text = '') {
  if (!text) return ''

  let localized = String(text)
    .replace('Personalized AI Fitness Plan', '个性化 AI 健身计划')
    .replace('General safety: keep intensity comfortable and stop if pain increases.', '通用安全建议：保持舒适强度，如出现疼痛请停止训练。')
    .replace('Prepare knees, hips, shoulders, and breathing before the main set.', '先激活膝、髋、肩并调整呼吸，为主训练降低受伤风险。')
    .replace('Reduce soreness and record perceived exertion after training.', '降低酸痛感，并记录主观疲劳度，方便明天继续调整。')
    .replace('Sleep history is limited; plan uses conservative intensity.', '睡眠历史数据不足，本次计划采用保守强度。')
    .replace('Free mode uses the shared fitness knowledge base for a general daily plan.', 'Free 使用通用健身知识库，生成适合多数人的基础训练建议。')
    .replace('The plan stays conservative and suitable for broad users.', '计划会保持保守强度，但不会建立你的个人专属知识库。')
    .replace('Pro mode uses longer history and more RAG citations for explainability.', 'Pro 模式使用更长历史窗口和更多 RAG 引用，解释链路更完整。')
    .replace('Today already has substantial training volume; prioritize recovery or mobility.', '今天训练量已经较高，建议优先恢复或灵活性训练。')
    .replace('Upgrade to Pro to unlock 30-day trend analysis and richer RAG citations.', '升级 Pro 可解锁 30 天趋势分析和更丰富的 RAG 引用。')

  localized = localized.replace(
    /Use a (\d+)-minute (\w+) session tailored to ([\w_]+)\./,
    (_, minutes, time, goal) => {
      const timeLabel = time === 'evening' ? '晚上' : time === 'today' ? '今天' : time
      return `建议在${timeLabel}完成 ${minutes} 分钟训练，目标聚焦${GOAL_LABELS[goal] || goal}。`
    }
  )
  localized = localized.replace(
    /Reported limitation: (.+)\. Keep impact low and stop if pain increases\./,
    (_, injury) => `已记录限制：${injury}。保持低冲击训练，如疼痛增加立即停止。`
  )
  localized = localized.replace(
    /Recent average workout: ([\d.]+) min\/day\./,
    (_, value) => `近期平均运动：${value} 分钟/天。`
  )
  localized = localized.replace(
    /Recent average sleep: ([\d.]+) h\/day\./,
    (_, value) => `近期平均睡眠：${value} 小时/天。`
  )
  localized = localized.replace(
    /Recent average sleep is ([\d.]+)h, so intensity should stay moderate\./,
    (_, value) => `近期平均睡眠为 ${value} 小时，训练强度应控制在中等或以下。`
  )
  localized = localized.replace(
    /Recent average diet intake: ([\d.]+) kcal\/day\./,
    (_, value) => `近期平均饮食摄入：${value} 千卡/天。`
  )
  localized = localized.replace(
    /Match the ([\w_]+) level; keep reps smooth and leave 2-3 reps in reserve\./,
    (_, level) => `匹配${level === 'beginner' ? '初学者' : level}水平，动作保持平稳，每组预留 2-3 次余力。`
  )

  Object.entries(GOAL_LABELS).forEach(([source, label]) => {
    localized = localized.replaceAll(source, label)
  })

  return localized
}

export function getPlanTierPresentation(tier = 'FREE') {
  if (tier === 'PRO') {
    return {
      title: 'Pro 私人顾问',
      badge: 'COACH',
      cta: '已开启 Pro',
      historyWindow: '30天趋势',
      citationLimit: '8条权威引用',
      description: '像私人健身顾问一样看懂你的训练、睡眠和饮食变化，给出更贴身的计划。'
    }
  }

  return {
    title: 'Free 体验版',
    badge: 'BASIC',
    cta: '升级为 Pro',
    historyWindow: '7天数据',
    citationLimit: '2条引用',
    description: '快速生成今日训练建议，适合先体验；升级后拥有专属 AI 私人健身顾问。'
  }
}
