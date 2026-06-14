import assert from "node:assert/strict";
import test from "node:test";

import {
  formatAiPlanForDisplay,
  getPlanTierPresentation,
  getRealRagCitations,
  localizeAiPlanText,
  localizePlanActivity,
  localizePlanIntensity,
  localizePlanStage,
} from "../src/utils/aiPlanFormatter.mjs";

test("formats personalized AI plan with risks, items, citations, and membership", () => {
  const text = formatAiPlanForDisplay({
    membershipTier: "PRO",
    summary: "Train for 35 minutes tonight.",
    riskFlags: ["Keep knee impact low."],
    personalInsights: ["Recent average workout: 25 min/day."],
    items: [
      { stage: "Warm-up", activity: "Mobility", minutes: 6, intensity: "low", notes: "Easy pace." },
    ],
    citations: [
      { source: "WHO", title: "Physical activity guidelines", url: "https://example.com" },
    ],
  });

  assert.match(text, /PRO/);
  assert.match(text, /Train for 35 minutes/);
  assert.match(text, /Keep knee impact low/);
  assert.match(text, /Warm-up/);
  assert.match(text, /WHO/);
});

test("prefers real rag metadata citations over legacy fixed citations", () => {
  const citations = getRealRagCitations({
    citations: [{ source: "Legacy", title: "Fixed list" }],
    ragMetadata: {
      citations: [
        {
          chunkId: "who-1",
          source: "WHO",
          title: "Adult activity",
          url: "https://example.com/who",
          authorityLevel: 5,
          rerankScore: 0.91,
          excerptChunk: "Adults benefit from weekly aerobic and strength activity.",
        },
      ],
    },
  });

  assert.equal(citations.length, 1);
  assert.equal(citations[0].chunkId, "who-1");
  assert.equal(citations[0].source, "WHO");
  assert.equal(citations[0].authorityLevel, 5);
});

test("describes visible Free and Pro differences for the plan module", () => {
  const free = getPlanTierPresentation("FREE");
  const pro = getPlanTierPresentation("PRO");

  assert.match(free.title, /Free/);
  assert.match(free.cta, /Pro/);
  assert.equal(free.historyWindow, "7天数据");
  assert.equal(free.citationLimit, "2条引用");

  assert.match(pro.title, /Pro/);
  assert.equal(pro.historyWindow, "30天趋势");
  assert.equal(pro.citationLimit, "8条权威引用");
  assert.match(pro.description, /私人健身顾问/);
  assert.match(pro.badge, /COACH/);
});

test("localizes generated AI plan fields for product display", () => {
  assert.equal(localizePlanStage("Warm-up"), "热身激活");
  assert.equal(localizePlanIntensity("low-to-moderate"), "低到中等强度");
  assert.equal(
    localizePlanActivity("yoga mat, resistance band circuit for fat_loss"),
    "瑜伽垫, 弹力带 循环训练： 减脂"
  );
  assert.equal(
    localizeAiPlanText("Use a 30-minute evening session tailored to fat_loss."),
    "建议在晚上完成 30 分钟训练，目标聚焦减脂。"
  );
  assert.match(
    localizeAiPlanText("Recent average sleep is 6.5h, so intensity should stay moderate."),
    /训练强度/
  );
});
