import assert from "node:assert/strict";
import test from "node:test";

import { buildPersonalizedPlanRequest } from "../src/modules/plans/personalized.js";

test("free members get a limited personalized-plan request with an upgrade hint", () => {
  const request = buildPersonalizedPlanRequest({
    membershipTier: "FREE",
    requestedDays: 30,
    profile: {
      goal: "fat_loss",
      fitnessLevel: "beginner",
      injuries: "knee discomfort",
      equipment: ["yoga mat"],
      preferredWorkoutTime: "evening",
    },
  });

  assert.equal(request.historyDays, 7);
  assert.equal(request.citationLimit, 2);
  assert.equal(request.includeTrendAnalysis, false);
  assert.match(request.upgradeHint, /Pro/);
});

test("pro members get deeper history, richer citations, and trend analysis", () => {
  const request = buildPersonalizedPlanRequest({
    membershipTier: "PRO",
    requestedDays: 30,
    profile: {
      goal: "muscle_gain",
      fitnessLevel: "intermediate",
      injuries: "",
      equipment: ["dumbbell", "resistance band"],
      preferredWorkoutTime: "morning",
    },
  });

  assert.equal(request.historyDays, 30);
  assert.equal(request.citationLimit, 8);
  assert.equal(request.includeTrendAnalysis, true);
  assert.equal(request.upgradeHint, "");
});
