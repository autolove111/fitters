import type { Prisma } from "@prisma/client";
import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { env } from "../../config/env.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { ensureSubscription } from "../membership/router.js";
import { buildPersonalizedPlanRequest } from "./personalized.js";

export const plansRouter = Router();

const todayWorkoutPlanSchema = z.object({
  days: z.number().int().min(1).max(30).default(7).optional(),
  goal: z.string().trim().min(1).max(64).optional(),
  availableMinutes: z.number().int().positive().max(240).optional(),
  preferredTime: z.enum(["morning", "afternoon", "evening"]).optional(),
  injuries: z.string().trim().max(255).optional(),
  equipment: z.array(z.string().trim().min(1).max(64)).max(20).optional(),
});

const personalizedWorkoutPlanSchema = z.object({
  requestedDays: z.number().int().min(1).max(30).default(7).optional(),
  goal: z.string().trim().min(1).max(64).optional(),
  availableMinutes: z.number().int().positive().max(240).optional(),
  preferredTime: z.enum(["morning", "afternoon", "evening"]).optional(),
  injuries: z.string().trim().max(255).optional(),
  equipment: z.array(z.string().trim().min(1).max(64)).max(20).optional(),
  question: z.string().trim().max(500).optional(),
});

plansRouter.use(requireAuth);

plansRouter.post(
  "/today-workout",
  asyncHandler(async (req, res) => {
    const authorization = req.header("Authorization") || "";
    if (!authorization.trim()) {
      throw new HttpError(401, "Missing authorization token");
    }

    const body = todayWorkoutPlanSchema.parse(req.body);
    const response = await fetch(`${env.aiServiceUrl}/plans/today-workout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: authorization,
        "X-Internal-Secret": env.aiServiceSecret,
      },
      body: JSON.stringify(body),
    });

    const payload = (await response.json().catch(() => null)) as
      | { code?: number; message?: string; data?: unknown }
      | null;

    if (!response.ok) {
      throw new HttpError(response.status, payload?.message || "AI service request failed");
    }

    ok(res, payload?.data ?? payload);
  }),
);

plansRouter.post(
  "/personalized-workout",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const authorization = req.header("Authorization") || "";
    if (!authorization.trim()) {
      throw new HttpError(401, "Missing authorization token");
    }

    const body = personalizedWorkoutPlanSchema.parse(req.body);
    const subscription = await ensureSubscription(userId);
    if (subscription.usedAiQuota >= subscription.dailyAiQuota) {
      throw new HttpError(429, "Daily AI plan quota has been used up");
    }

    const profile = await prisma.userFitnessProfile.findUnique({ where: { userId } });
    const profileSnapshot = {
      age: profile?.age ?? null,
      heightCm: profile?.heightCm ?? null,
      weightKg: profile?.weightKg ? Number(profile.weightKg) : null,
      goal: body.goal ?? profile?.goal ?? "general_fitness",
      fitnessLevel: profile?.fitnessLevel ?? "beginner",
      injuries: body.injuries ?? profile?.injuries ?? "",
      equipment: body.equipment ?? (Array.isArray(profile?.equipment) ? profile?.equipment as string[] : []),
      preferredWorkoutTime: body.preferredTime ?? profile?.preferredWorkoutTime ?? "evening",
    };

    const planRequest = buildPersonalizedPlanRequest({
      membershipTier: subscription.tier,
      requestedDays: body.requestedDays ?? undefined,
      profile: profileSnapshot,
    });

    const outboundPayload = {
      ...body,
      ...planRequest,
      membership: {
        tier: subscription.tier,
        dailyAiQuota: subscription.dailyAiQuota,
        usedAiQuota: subscription.usedAiQuota,
      },
    };

    const response = await fetch(`${env.aiServiceUrl}/plans/personalized-workout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: authorization,
        "X-Internal-Secret": env.aiServiceSecret,
      },
      body: JSON.stringify(outboundPayload),
    });

    const payload = (await response.json().catch(() => null)) as
      | { code?: number; message?: string; data?: any }
      | null;

    if (!response.ok) {
      throw new HttpError(response.status, payload?.message || "AI service request failed");
    }

    const data = payload?.data ?? payload;
    await prisma.$transaction([
      prisma.userSubscription.update({
        where: { userId },
        data: { usedAiQuota: { increment: 1 } },
      }),
      prisma.aiPlanHistory.create({
        data: {
          userId,
          membershipTier: subscription.tier,
          request: outboundPayload as unknown as Prisma.InputJsonValue,
          response: data as Prisma.InputJsonValue,
          citations: (data?.citations ?? []) as Prisma.InputJsonValue,
        },
      }),
    ]);

    ok(res, {
      ...data,
      membership: {
        tier: subscription.tier,
        remainingAiQuota: Math.max(0, subscription.dailyAiQuota - subscription.usedAiQuota - 1),
      },
      upgradeHint: planRequest.upgradeHint || data?.upgradeHint || "",
    });
  }),
);
