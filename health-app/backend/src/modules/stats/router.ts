import { GoalPeriod, GoalType } from "@prisma/client";
import { Router } from "express";
import { asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { addDays, formatDate, todayUtc } from "../../utils/dates.js";

export const statsRouter = Router();

function toNumber(value: any): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'bigint') return Number(value);
  if (typeof value === 'number') return value;
  if (value.toNumber) return value.toNumber();
  return Number(value);
}

statsRouter.use(requireAuth);

statsRouter.get(
  "/today",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const today = todayUtc();
    const tomorrow = addDays(today, 1);

    const [goal, workoutAggregate, sleepAggregate, mealAggregate] = await Promise.all([
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
      prisma.sleepRecord.aggregate({
        where: { userId, recordDate: { gte: today, lt: tomorrow } },
        _avg: { quality: true },
        _count: true,
      }),
      prisma.mealItem.aggregate({
        where: { meal: { userId, mealDate: { gte: today, lt: tomorrow } } },
        _sum: { calories: true },
        _count: true,
      }),
    ]);

    const targetMinutes = goal?.targetValue ?? 0;
    const completedMinutes = workoutAggregate._sum.durationMinutes ?? 0;
    ok(res, {
      date: formatDate(today),
      targetMinutes,
      completedMinutes,
      completedCalories: workoutAggregate._sum.calories ?? 0,
      workoutCount: workoutAggregate._count,
      sleepCount: sleepAggregate._count,
      avgSleepQuality: toNumber(sleepAggregate._avg.quality) ?? 0,
      mealCalories: mealAggregate._sum.calories ?? 0,
      mealItemCount: mealAggregate._count,
      completionPercent: targetMinutes > 0 ? Math.min(100, Math.round((completedMinutes / targetMinutes) * 100)) : 0,
    });
  }),
);

statsRouter.get(
  "/weekly",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const end = todayUtc();
    const start = addDays(end, -6);

    const [workoutRecords, sleepRecords, mealItems] = await Promise.all([
      prisma.workoutRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) } },
        select: { recordDate: true, durationMinutes: true, calories: true },
      }),
      prisma.sleepRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) } },
        select: { recordDate: true, quality: true },
      }),
      prisma.mealItem.findMany({
        where: { meal: { userId, mealDate: { gte: start, lt: addDays(end, 1) } } },
        select: { meal: { select: { mealDate: true } }, calories: true },
      }),
    ]);

    const minutesByDate = new Map<string, number>();
    const caloriesByDate = new Map<string, number>();
    const sleepQualityByDate = new Map<string, { sum: number; count: number }>();
    const mealCaloriesByDate = new Map<string, number>();

    for (const record of workoutRecords) {
      const date = formatDate(record.recordDate);
      minutesByDate.set(date, (minutesByDate.get(date) || 0) + record.durationMinutes);
      caloriesByDate.set(date, (caloriesByDate.get(date) || 0) + record.calories);
    }

    for (const record of sleepRecords) {
      const date = formatDate(record.recordDate);
      const current = sleepQualityByDate.get(date) || { sum: 0, count: 0 };
      sleepQualityByDate.set(date, { sum: current.sum + record.quality, count: current.count + 1 });
    }

    for (const item of mealItems) {
      const date = formatDate(item.meal.mealDate);
      mealCaloriesByDate.set(date, (mealCaloriesByDate.get(date) || 0) + item.calories);
    }

    const days = Array.from({ length: 7 }, (_, index) => {
      const date = formatDate(addDays(start, index));
      const sleepStats = sleepQualityByDate.get(date);
      return {
        date,
        workoutMinutes: minutesByDate.get(date) || 0,
        workoutCalories: caloriesByDate.get(date) || 0,
        avgSleepQuality: sleepStats ? Math.round(sleepStats.sum / sleepStats.count) : 0,
        mealCalories: mealCaloriesByDate.get(date) || 0,
      };
    });

    ok(res, days);
  }),
);

statsRouter.get(
  "/history",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const requestedDays = Number(req.query.days ?? 30);
    const days = Math.min(Math.max(requestedDays, 1), 90);
    const end = todayUtc();
    const start = addDays(end, -(days - 1));

    const [workoutGoal, sleepGoal, dietGoal, workoutRecords, sleepRecords, dietRecords] = await Promise.all([
      prisma.goal.findUnique({
        where: {
          userId_goalType_period: {
            userId,
            goalType: GoalType.DAILY_WORKOUT_MINUTES,
            period: GoalPeriod.DAILY,
          },
        },
      }),
      prisma.goal.findUnique({
        where: {
          userId_goalType_period: {
            userId,
            goalType: GoalType.DAILY_SLEEP_HOURS,
            period: GoalPeriod.DAILY,
          },
        },
      }),
      prisma.goal.findUnique({
        where: {
          userId_goalType_period: {
            userId,
            goalType: GoalType.DAILY_DIET_CALORIES,
            period: GoalPeriod.DAILY,
          },
        },
      }),
      prisma.workoutRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) } },
        select: { recordDate: true, durationMinutes: true, calories: true },
      }),
      prisma.sleepRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) } },
        select: { recordDate: true, durationHours: true },
      }),
      prisma.dietRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) } },
        select: { recordDate: true, calories: true },
      }),
    ]);

    const workoutByDate = new Map<string, { minutes: number; calories: number }>();
    const sleepByDate = new Map<string, number>();
    const dietByDate = new Map<string, number>();

    for (const record of workoutRecords) {
      const date = formatDate(record.recordDate);
      const current = workoutByDate.get(date) || { minutes: 0, calories: 0 };
      workoutByDate.set(date, {
        minutes: current.minutes + record.durationMinutes,
        calories: current.calories + record.calories,
      });
    }

    for (const record of sleepRecords) {
      const date = formatDate(record.recordDate);
      sleepByDate.set(date, (sleepByDate.get(date) || 0) + (toNumber(record.durationHours) || 0));
    }

    for (const record of dietRecords) {
      const date = formatDate(record.recordDate);
      dietByDate.set(date, (dietByDate.get(date) || 0) + record.calories);
    }

    const workoutTarget = workoutGoal?.targetValue ?? 30;
    const sleepTarget = sleepGoal?.targetValue ?? 8;
    const dietTarget = dietGoal?.targetValue ?? 2000;

    const daysList = Array.from({ length: days }, (_, index) => {
      const date = formatDate(addDays(start, index));
      return {
        date,
        workoutMinutes: workoutByDate.get(date)?.minutes ?? 0,
        workoutCalories: workoutByDate.get(date)?.calories ?? 0,
        sleepHours: sleepByDate.get(date) ?? 0,
        dietCalories: dietByDate.get(date) ?? 0,
        workoutTarget,
        sleepTarget,
        dietTarget,
      };
    });

    ok(res, daysList);
  }),
);

statsRouter.get(
  "/summary",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    
    const [workoutAggregate, sleepAggregate, mealAggregate, dietAggregate] = await Promise.all([
      prisma.workoutRecord.aggregate({
        where: { userId },
        _sum: { durationMinutes: true, calories: true },
        _count: true,
      }),
      prisma.sleepRecord.aggregate({
        where: { userId },
        _avg: { quality: true },
        _count: true,
      }),
      prisma.mealItem.aggregate({
        where: { meal: { userId } },
        _sum: { calories: true },
        _count: true,
      }),
      prisma.dietRecord.aggregate({
        where: { userId },
        _sum: { calories: true },
        _count: true,
      }),
    ]);

    ok(res, {
      workoutCount: workoutAggregate._count,
      totalWorkoutMinutes: workoutAggregate._sum.durationMinutes ?? 0,
      totalWorkoutCalories: workoutAggregate._sum.calories ?? 0,
      sleepCount: sleepAggregate._count,
      avgSleepQuality: toNumber(sleepAggregate._avg.quality) ?? 0,
      mealItemCount: mealAggregate._count,
      totalMealCalories: mealAggregate._sum.calories ?? 0,
      dietRecordCount: dietAggregate._count,
      totalDietCalories: dietAggregate._sum.calories ?? 0,
    });
  }),
);

statsRouter.get(
  "/sleep/today",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const today = todayUtc();
    const tomorrow = addDays(today, 1);

    const [goal, aggregate] = await Promise.all([
      prisma.goal.findUnique({
        where: {
          userId_goalType_period: {
            userId,
            goalType: GoalType.DAILY_SLEEP_HOURS,
            period: GoalPeriod.DAILY,
          },
        },
      }),
      prisma.sleepRecord.findMany({
        where: { userId, recordDate: { gte: today, lt: tomorrow } },
        orderBy: { createdAt: "desc" },
      }),
    ]);

    const records = aggregate.map((record) => ({
      id: record.id,
      sleepTime: record.sleepTime.toISOString(),
      wakeTime: record.wakeTime.toISOString(),
      quality: record.quality,
      durationHours: toNumber(record.durationHours) ?? 0,
    }));

    ok(res, {
      date: formatDate(today),
      targetHours: goal?.targetValue ?? 8,
      records,
    });
  }),
);

statsRouter.get(
  "/diet/today",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const today = todayUtc();
    const tomorrow = addDays(today, 1);

    const [goal, dietRecords, meals] = await Promise.all([
      prisma.goal.findUnique({
        where: {
          userId_goalType_period: {
            userId,
            goalType: GoalType.DAILY_DIET_CALORIES,
            period: GoalPeriod.DAILY,
          },
        },
      }),
      prisma.dietRecord.findMany({
        where: { userId, recordDate: { gte: today, lt: tomorrow } },
        orderBy: { createdAt: "desc" },
      }),
      prisma.meal.findMany({
        where: { userId, mealDate: { gte: today, lt: tomorrow } },
        include: { items: true },
        orderBy: { createdAt: "desc" },
      }),
    ]);

    const dietCalories = dietRecords.reduce((sum, record) => sum + record.calories, 0);
    const mealCalories = meals.reduce((sum, meal) => {
      return sum + meal.items.reduce((itemSum, item) => itemSum + item.calories, 0);
    }, 0);

    const totalCalories = dietCalories + mealCalories;
    const targetCalories = goal?.targetValue ?? 2000;

    ok(res, {
      date: formatDate(today),
      targetCalories,
      totalCalories,
      dietCalories,
      mealCalories,
      completionPercent: targetCalories > 0 ? Math.min(100, Math.round((totalCalories / targetCalories) * 100)) : 0,
      dietRecords: dietRecords.map((r) => ({
        id: r.id,
        type: r.type,
        calories: r.calories,
        notes: r.notes,
      })),
      meals: meals.map((m) => ({
        id: m.id,
        mealType: m.mealType,
        calories: m.items.reduce((sum, item) => sum + item.calories, 0),
        items: m.items.length,
      })),
    });
  }),
);
