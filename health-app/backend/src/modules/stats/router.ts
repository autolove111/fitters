import { GoalPeriod, GoalType } from "@prisma/client";
import { Router } from "express";
import { asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { addDays, formatDate, todayUtc } from "../../utils/dates.js";

export const statsRouter = Router();

statsRouter.use(requireAuth);

statsRouter.get(
  "/today",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const today = todayUtc();
    const tomorrow = addDays(today, 1);

    const [goal, aggregate] = await Promise.all([
      prisma.goal.findUnique({
        where: {
          userId_goalType_period: {
            userId,
            goalType: GoalType.DAILY_WORKOUT_MINUTES,
            period: GoalPeriod.DAILY,
          },
        },
      }),
      prisma.workoutRecord.aggregate({
        where: { userId, recordDate: { gte: today, lt: tomorrow } },
        _sum: { durationMinutes: true, calories: true },
        _count: true,
      }),
    ]);

    const targetMinutes = goal?.targetValue ?? 0;
    const completedMinutes = aggregate._sum.durationMinutes ?? 0;
    ok(res, {
      date: formatDate(today),
      targetMinutes,
      completedMinutes,
      completedCalories: aggregate._sum.calories ?? 0,
      workoutCount: aggregate._count,
      completionPercent: targetMinutes > 0 ? Math.min(100, Math.round((completedMinutes / targetMinutes) * 100)) : 0,
    });
  }),
);

statsRouter.get(
  "/workouts/weekly",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const end = todayUtc();
    const start = addDays(end, -6);
    const records = await prisma.workoutRecord.findMany({
      where: { userId, recordDate: { gte: start, lt: addDays(end, 1) } },
      select: { recordDate: true, durationMinutes: true },
    });

    const minutesByDate = new Map<string, number>();
    for (const record of records) {
      const date = formatDate(record.recordDate);
      minutesByDate.set(date, (minutesByDate.get(date) || 0) + record.durationMinutes);
    }

    const days = Array.from({ length: 7 }, (_, index) => {
      const date = formatDate(addDays(start, index));
      return { date, minutes: minutesByDate.get(date) || 0 };
    });

    ok(res, days);
  }),
);

statsRouter.get(
  "/summary",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const aggregate = await prisma.workoutRecord.aggregate({
      where: { userId },
      _sum: { durationMinutes: true, calories: true },
      _count: true,
    });

    ok(res, {
      count: aggregate._count,
      totalMinutes: aggregate._sum.durationMinutes ?? 0,
      totalCalories: aggregate._sum.calories ?? 0,
    });
  }),
);
