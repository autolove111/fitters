import { GoalPeriod, GoalType } from "@prisma/client";
import { Router } from "express";
import { z } from "zod";
import { asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";

export const goalsRouter = Router();

const goalSchema = z.object({
  targetValue: z.number().int().positive(),
  goalType: z.nativeEnum(GoalType).default(GoalType.DAILY_WORKOUT_MINUTES),
  period: z.nativeEnum(GoalPeriod).default(GoalPeriod.DAILY),
});

goalsRouter.use(requireAuth);

goalsRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = goalSchema.parse(req.body);
    const goal = await prisma.goal.upsert({
      where: {
        userId_goalType_period: {
          userId,
          goalType: body.goalType,
          period: body.period,
        },
      },
      update: { targetValue: body.targetValue },
      create: {
        userId,
        goalType: body.goalType,
        period: body.period,
        targetValue: body.targetValue,
      },
    });

    ok(res, {
      id: goal.id,
      goalType: goal.goalType,
      targetValue: goal.targetValue,
      period: goal.period,
      updatedAt: goal.updatedAt.toISOString(),
    });
  }),
);
