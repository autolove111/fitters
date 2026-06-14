import { MembershipTier } from "@prisma/client";
import { Router } from "express";
import { z } from "zod";
import { asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { formatDate, todayUtc } from "../../utils/dates.js";

export const membershipRouter = Router();

const mockTierSchema = z.object({
  tier: z.nativeEnum(MembershipTier),
});

function quotaForTier(tier: MembershipTier) {
  return tier === MembershipTier.PRO ? 20 : 3;
}

export async function ensureSubscription(userId: number) {
  const today = todayUtc();
  const existing = await prisma.userSubscription.findUnique({ where: { userId } });
  if (!existing) {
    return prisma.userSubscription.create({
      data: { userId, tier: MembershipTier.FREE, dailyAiQuota: quotaForTier(MembershipTier.FREE), quotaDate: today },
    });
  }

  if (formatDate(existing.quotaDate) !== formatDate(today)) {
    return prisma.userSubscription.update({
      where: { userId },
      data: { usedAiQuota: 0, dailyAiQuota: quotaForTier(existing.tier), quotaDate: today },
    });
  }

  return existing;
}

membershipRouter.use(requireAuth);

membershipRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const subscription = await ensureSubscription(userId);
    ok(res, {
      tier: subscription.tier,
      dailyAiQuota: subscription.dailyAiQuota,
      usedAiQuota: subscription.usedAiQuota,
      remainingAiQuota: Math.max(0, subscription.dailyAiQuota - subscription.usedAiQuota),
      quotaDate: formatDate(subscription.quotaDate),
      benefits:
        subscription.tier === MembershipTier.PRO
          ? ["30-day trend analysis", "5 RAG citations", "risk-aware plan details"]
          : ["7-day basic plan", "2 RAG citations", "upgrade prompt"],
    });
  }),
);

membershipRouter.put(
  "/mock-tier",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = mockTierSchema.parse(req.body);
    const subscription = await prisma.userSubscription.upsert({
      where: { userId },
      update: { tier: body.tier, dailyAiQuota: quotaForTier(body.tier), usedAiQuota: 0, quotaDate: todayUtc() },
      create: { userId, tier: body.tier, dailyAiQuota: quotaForTier(body.tier), quotaDate: todayUtc() },
    });

    ok(res, {
      tier: subscription.tier,
      dailyAiQuota: subscription.dailyAiQuota,
      usedAiQuota: subscription.usedAiQuota,
      remainingAiQuota: subscription.dailyAiQuota - subscription.usedAiQuota,
      quotaDate: formatDate(subscription.quotaDate),
    }, "updated");
  }),
);
