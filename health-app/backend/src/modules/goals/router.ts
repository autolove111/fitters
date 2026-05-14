import { GoalPeriod, GoalType } from "@prisma/client";
import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";

export const goalsRouter = Router();

const goalSchema = z.object({
  targetValue: z.number().int().positive(),
  goalType: z.nativeEnum(GoalType).default(GoalType.DAILY_WORKOUT_MINUTES),
  period: z.nativeEnum(GoalPeriod).default(GoalPeriod.DAILY),
});

function serializeGoal(goal: any) {
  return {
    id: goal.id,
    goalType: goal.goalType,
    targetValue: goal.targetValue,
    period: goal.period,
    createdAt: goal.createdAt.toISOString(),
    updatedAt: goal.updatedAt.toISOString(),
  };
}

goalsRouter.use(requireAuth);

goalsRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const { goalType, period } = req.query;
    
    const where: any = { userId };
    if (goalType) {
      where.goalType = goalType as GoalType;
    }
    if (period) {
      where.period = period as GoalPeriod;
    }
    
    const goals = await prisma.goal.findMany({
      where,
      orderBy: { updatedAt: "desc" },
    });
    
    ok(res, goals.map(serializeGoal));
  }),
);

goalsRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid goal id");
    }
    
    const goal = await prisma.goal.findUnique({ where: { id } });
    if (!goal) {
      throw new HttpError(404, "goal not found");
    }
    
    if (goal.userId !== userId) {
      throw new HttpError(403, "cannot access another user's goal");
    }
    
    ok(res, serializeGoal(goal));
  }),
);

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

    ok(res, serializeGoal(goal), "created");
  }),
);

goalsRouter.put(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid goal id");
    }
    
    const goal = await prisma.goal.findUnique({ where: { id } });
    if (!goal) {
      throw new HttpError(404, "goal not found");
    }
    
    if (goal.userId !== userId) {
      throw new HttpError(403, "cannot modify another user's goal");
    }
    
    const body = goalSchema.partial().parse(req.body);
    
    const data: any = {};
    if (body.targetValue !== undefined) {
      data.targetValue = body.targetValue;
    }
    if (body.goalType) {
      data.goalType = body.goalType;
    }
    if (body.period) {
      data.period = body.period;
    }
    
    const updatedGoal = await prisma.goal.update({
      where: { id },
      data,
    });
    
    ok(res, serializeGoal(updatedGoal), "updated");
  }),
);

goalsRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid goal id");
    }
    
    const goal = await prisma.goal.findUnique({ where: { id } });
    if (!goal) {
      throw new HttpError(404, "goal not found");
    }
    
    if (goal.userId !== userId) {
      throw new HttpError(403, "cannot delete another user's goal");
    }
    
    await prisma.goal.delete({ where: { id } });
    ok(res, null, "deleted");
  }),
);
