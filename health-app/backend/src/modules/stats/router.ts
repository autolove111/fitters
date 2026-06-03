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
  if (typeof value === "bigint") return Number(value);
  if (typeof value === "number") return value;
  if (value.toNumber) return value.toNumber();
  return Number(value);
}

function isWorkoutRecord(type: string) {
  return type !== "wechat_steps" && type !== "wechat_steps_sync";
}

statsRouter.use(requireAuth);

statsRouter.get(
  "/today",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const today = todayUtc();
    const tomorrow = addDays(today, 1);

    const [goal, workoutRecords, sleepAggregate, dietRecords, stepsRecord] = await Promise.all([
      prisma.goal.findUnique({
        where: {
          userId_goalType_period: {
            userId,
            goalType: GoalType.DAILY_WORKOUT_MINUTES,
            period: GoalPeriod.DAILY,
          },
        },
      }),
      prisma.workoutRecord.findMany({
        where: { userId, recordDate: { gte: today, lt: tomorrow } },
      }),
      prisma.sleepRecord.aggregate({
        where: { userId, recordDate: { gte: today, lt: tomorrow } },
        _avg: { quality: true },
        _count: true,
      }),
      prisma.dietRecord.findMany({
        where: {
          userId,
          recordDate: { gte: today, lt: tomorrow },
          recordType: { in: ["diet", "meal_item", "hydration", "weight"] },
        },
      }),
      prisma.workoutRecord.findFirst({
        where: { userId, type: "wechat_steps", sourceType: "WECHAT_WERUN", recordDate: today },
      }),
    ]);

    const realWorkouts = workoutRecords.filter((record) => isWorkoutRecord(record.type));
    const targetMinutes = goal?.targetValue ?? 0;
    const completedMinutes = realWorkouts.reduce((sum, record) => sum + record.durationMinutes, 0);
    const completedCalories = realWorkouts.reduce((sum, record) => sum + record.calories, 0);
    const mealCalories = dietRecords
      .filter((record) => record.recordType === "diet" || record.recordType === "meal_item")
      .reduce((sum, record) => sum + record.calories, 0);
    const hydrationMl = dietRecords
      .filter((record) => record.recordType === "hydration")
      .reduce((sum, record) => sum + (record.amountMl || 0), 0);
    const weightRecord = dietRecords.find((record) => record.recordType === "weight");

    ok(res, {
      date: formatDate(today),
      targetMinutes,
      completedMinutes,
      completedCalories,
      workoutCount: realWorkouts.length,
      steps: stepsRecord?.steps ?? 0,
      hydrationMl,
      weightKg: toNumber(weightRecord?.weightKg) ?? null,
      sleepCount: sleepAggregate._count,
      avgSleepQuality: toNumber(sleepAggregate._avg.quality) ?? 0,
      mealCalories,
      mealItemCount: dietRecords.filter((record) => record.recordType === "meal_item").length,
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

    const [workoutRecords, sleepRecords, dietRecords] = await Promise.all([
      prisma.workoutRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) } },
        select: { recordDate: true, type: true, durationMinutes: true, calories: true, steps: true },
      }),
      prisma.sleepRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) } },
        select: { recordDate: true, quality: true },
      }),
      prisma.dietRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) }, recordType: { in: ["diet", "meal_item"] } },
        select: { recordDate: true, calories: true },
      }),
    ]);

    const minutesByDate = new Map<string, number>();
    const caloriesByDate = new Map<string, number>();
    const stepsByDate = new Map<string, number>();
    const sleepQualityByDate = new Map<string, { sum: number; count: number }>();
    const mealCaloriesByDate = new Map<string, number>();

    for (const record of workoutRecords) {
      const date = formatDate(record.recordDate);
      if (record.type === "wechat_steps") {
        stepsByDate.set(date, record.steps || 0);
      } else if (isWorkoutRecord(record.type)) {
        minutesByDate.set(date, (minutesByDate.get(date) || 0) + record.durationMinutes);
        caloriesByDate.set(date, (caloriesByDate.get(date) || 0) + record.calories);
      }
    }

    for (const record of sleepRecords) {
      const date = formatDate(record.recordDate);
      const current = sleepQualityByDate.get(date) || { sum: 0, count: 0 };
      sleepQualityByDate.set(date, { sum: current.sum + record.quality, count: current.count + 1 });
    }

    for (const record of dietRecords) {
      const date = formatDate(record.recordDate);
      mealCaloriesByDate.set(date, (mealCaloriesByDate.get(date) || 0) + record.calories);
    }

    const days = Array.from({ length: 7 }, (_, index) => {
      const date = formatDate(addDays(start, index));
      const sleepStats = sleepQualityByDate.get(date);
      return {
        date,
        workoutMinutes: minutesByDate.get(date) || 0,
        workoutCalories: caloriesByDate.get(date) || 0,
        steps: stepsByDate.get(date) || 0,
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
        select: { recordDate: true, type: true, durationMinutes: true, calories: true, steps: true },
      }),
      prisma.sleepRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) } },
        select: { recordDate: true, durationHours: true },
      }),
      prisma.dietRecord.findMany({
        where: { userId, recordDate: { gte: start, lt: addDays(end, 1) }, recordType: { in: ["diet", "meal_item", "hydration", "weight"] } },
        select: { recordDate: true, recordType: true, calories: true, amountMl: true, weightKg: true },
      }),
    ]);

    const workoutByDate = new Map<string, { minutes: number; calories: number; steps: number }>();
    const sleepByDate = new Map<string, number>();
    const dietByDate = new Map<string, { calories: number; hydrationMl: number; weightKg: number | null }>();

    for (const record of workoutRecords) {
      const date = formatDate(record.recordDate);
      const current = workoutByDate.get(date) || { minutes: 0, calories: 0, steps: 0 };
      if (record.type === "wechat_steps") {
        current.steps = record.steps || 0;
      } else if (isWorkoutRecord(record.type)) {
        current.minutes += record.durationMinutes;
        current.calories += record.calories;
      }
      workoutByDate.set(date, current);
    }

    for (const record of sleepRecords) {
      const date = formatDate(record.recordDate);
      sleepByDate.set(date, (sleepByDate.get(date) || 0) + (toNumber(record.durationHours) || 0));
    }

    for (const record of dietRecords) {
      const date = formatDate(record.recordDate);
      const current = dietByDate.get(date) || { calories: 0, hydrationMl: 0, weightKg: null };
      if (record.recordType === "diet" || record.recordType === "meal_item") {
        current.calories += record.calories;
      } else if (record.recordType === "hydration") {
        current.hydrationMl += record.amountMl || 0;
      } else if (record.recordType === "weight") {
        current.weightKg = toNumber(record.weightKg);
      }
      dietByDate.set(date, current);
    }

    const workoutTarget = workoutGoal?.targetValue ?? 30;
    const sleepTarget = sleepGoal?.targetValue ?? 8;
    const dietTarget = dietGoal?.targetValue ?? 2000;

    const daysList = Array.from({ length: days }, (_, index) => {
      const date = formatDate(addDays(start, index));
      const workout = workoutByDate.get(date) || { minutes: 0, calories: 0, steps: 0 };
      const diet = dietByDate.get(date) || { calories: 0, hydrationMl: 0, weightKg: null };
      return {
        date,
        workoutMinutes: workout.minutes,
        workoutCalories: workout.calories,
        steps: workout.steps,
        sleepHours: sleepByDate.get(date) ?? 0,
        dietCalories: diet.calories,
        hydrationMl: diet.hydrationMl,
        weightKg: diet.weightKg,
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

    const [workouts, sleepAggregate, dietAggregate, mealItemAggregate] = await Promise.all([
      prisma.workoutRecord.findMany({ where: { userId } }),
      prisma.sleepRecord.aggregate({
        where: { userId },
        _avg: { quality: true },
        _count: true,
      }),
      prisma.dietRecord.aggregate({
        where: { userId, recordType: "diet" },
        _sum: { calories: true },
        _count: true,
      }),
      prisma.dietRecord.aggregate({
        where: { userId, recordType: "meal_item" },
        _sum: { calories: true },
        _count: true,
      }),
    ]);

    const realWorkouts = workouts.filter((record) => isWorkoutRecord(record.type));
    ok(res, {
      workoutCount: realWorkouts.length,
      totalWorkoutMinutes: realWorkouts.reduce((sum, record) => sum + record.durationMinutes, 0),
      totalWorkoutCalories: realWorkouts.reduce((sum, record) => sum + record.calories, 0),
      sleepCount: sleepAggregate._count,
      avgSleepQuality: toNumber(sleepAggregate._avg.quality) ?? 0,
      mealItemCount: mealItemAggregate._count,
      totalMealCalories: mealItemAggregate._sum.calories ?? 0,
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

    const [goal, records] = await Promise.all([
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

    ok(res, {
      date: formatDate(today),
      targetHours: goal?.targetValue ?? 8,
      records: records.map((record) => ({
        id: record.id,
        sleepTime: record.sleepTime.toISOString(),
        wakeTime: record.wakeTime.toISOString(),
        quality: record.quality,
        durationHours: toNumber(record.durationHours) ?? 0,
      })),
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
        where: { userId, recordType: "diet", recordDate: { gte: today, lt: tomorrow } },
        orderBy: { createdAt: "desc" },
      }),
      prisma.dietRecord.findMany({
        where: { userId, recordType: "meal", recordDate: { gte: today, lt: tomorrow } },
        include: { children: { where: { recordType: "meal_item" } } },
        orderBy: { createdAt: "desc" },
      }),
    ]);

    const dietCalories = dietRecords.reduce((sum, record) => sum + record.calories, 0);
    const mealCalories = meals.reduce((sum, meal) => {
      return sum + meal.children.reduce((itemSum, item) => itemSum + item.calories, 0);
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
        calories: m.children.reduce((sum, item) => sum + item.calories, 0),
        items: m.children.length,
      })),
    });
  }),
);
