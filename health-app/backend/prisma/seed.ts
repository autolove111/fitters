import bcrypt from "bcryptjs";
import { GoalPeriod, GoalType, MembershipTier, PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

function daysAgo(days: number) {
  const date = new Date();
  date.setUTCHours(0, 0, 0, 0);
  date.setUTCDate(date.getUTCDate() - days);
  return date;
}

function atUtc(days: number, hour: number, minute = 0) {
  const date = daysAgo(days);
  date.setUTCHours(hour, minute, 0, 0);
  return date;
}

async function main() {
  const passwordHash = await bcrypt.hash("demo123", 10);
  const user = await prisma.user.upsert({
    where: { account: "demo" },
    update: {},
    create: { account: "demo", passwordHash, nickname: "Demo User" },
  });

  await prisma.userFitnessProfile.upsert({
    where: { userId: user.id },
    update: {
      age: 22,
      heightCm: 175,
      weightKg: 72.5,
      goal: "fat_loss",
      fitnessLevel: "beginner",
      injuries: "knee discomfort after long runs",
      equipment: ["yoga mat", "resistance band"],
      preferredWorkoutTime: "evening",
    },
    create: {
      userId: user.id,
      age: 22,
      heightCm: 175,
      weightKg: 72.5,
      goal: "fat_loss",
      fitnessLevel: "beginner",
      injuries: "knee discomfort after long runs",
      equipment: ["yoga mat", "resistance band"],
      preferredWorkoutTime: "evening",
    },
  });

  await prisma.userSubscription.upsert({
    where: { userId: user.id },
    update: { tier: MembershipTier.PRO, dailyAiQuota: 20, usedAiQuota: 0, quotaDate: daysAgo(0) },
    create: { userId: user.id, tier: MembershipTier.PRO, dailyAiQuota: 20, quotaDate: daysAgo(0) },
  });

  await prisma.goal.upsert({
    where: {
      userId_goalType_period: {
        userId: user.id,
        goalType: GoalType.DAILY_WORKOUT_MINUTES,
        period: GoalPeriod.DAILY,
      },
    },
    update: { targetValue: 45 },
    create: {
      userId: user.id,
      goalType: GoalType.DAILY_WORKOUT_MINUTES,
      period: GoalPeriod.DAILY,
      targetValue: 45,
    },
  });

  await prisma.goal.upsert({
    where: {
      userId_goalType_period: {
        userId: user.id,
        goalType: GoalType.DAILY_SLEEP_HOURS,
        period: GoalPeriod.DAILY,
      },
    },
    update: { targetValue: 8 },
    create: {
      userId: user.id,
      goalType: GoalType.DAILY_SLEEP_HOURS,
      period: GoalPeriod.DAILY,
      targetValue: 8,
    },
  });

  await prisma.goal.upsert({
    where: {
      userId_goalType_period: {
        userId: user.id,
        goalType: GoalType.DAILY_DIET_CALORIES,
        period: GoalPeriod.DAILY,
      },
    },
    update: { targetValue: 2000 },
    create: {
      userId: user.id,
      goalType: GoalType.DAILY_DIET_CALORIES,
      period: GoalPeriod.DAILY,
      targetValue: 2000,
    },
  });

  await prisma.workoutRecord.deleteMany({ where: { userId: user.id } });
  const demoDays = 30;

  await prisma.workoutRecord.createMany({
    data: Array.from({ length: demoDays }, (_, index) => ({
      userId: user.id,
      type: index % 3 === 0 ? "strength" : index % 2 === 0 ? "running" : "cycling",
      durationMinutes: [24, 32, 38, 0, 45, 28, 50][index % 7],
      calories: [120, 180, 230, 0, 280, 160, 310][index % 7],
      recordDate: daysAgo(demoDays - 1 - index),
      sourceType: "MANUAL",
      notes: "demo seed data",
    })),
  });
  await prisma.workoutRecord.createMany({
    data: Array.from({ length: demoDays }, (_, index) => ({
      userId: user.id,
      type: "wechat_steps",
      durationMinutes: 0,
      calories: 0,
      steps: [5200, 6800, 7400, 6100, 8800, 9300, 10000][index % 7],
      sourceType: "WECHAT_WERUN",
      recordDate: daysAgo(demoDays - 1 - index),
      notes: "demo wechat steps",
    })),
  });

  await prisma.sleepRecord.deleteMany({ where: { userId: user.id } });
  await prisma.sleepRecord.createMany({
    data: Array.from({ length: demoDays }, (_, index) => {
      const days = demoDays - 1 - index;
      const durationHours = [6.4, 7.1, 7.4, 6.8, 7.8, 8.0, 7.2][index % 7];
      return {
        userId: user.id,
        recordDate: daysAgo(days),
        durationHours,
        deepHours: [1.2, 1.5, 1.7, 1.4, 1.9, 2.0, 1.6][index % 7],
        sleepTime: atUtc(days + 1, 23, index % 2 === 0 ? 10 : 35),
        wakeTime: atUtc(days, 6, 30 + (index % 3) * 10),
        quality: [68, 74, 78, 71, 84, 88, 80][index % 7],
        sourceType: "MANUAL",
        notes: "demo sleep data",
        metadata: { source: "seed" },
      };
    }),
  });

  await prisma.dietRecord.deleteMany({
    where: { OR: [{ userId: user.id }, { recordType: "food_catalog" }] },
  });

  await prisma.dietRecord.createMany({
    data: Array.from({ length: demoDays }, (_, index) => ({
      userId: user.id,
      recordType: "diet",
      type: index % 2 === 0 ? "balanced" : "high-protein",
      calories: [1820, 1960, 2070, 1880, 2140, 2010, 1930][index % 7],
      recordDate: daysAgo(demoDays - 1 - index),
      notes: "demo diet summary data",
    })),
  });

  const foods = await Promise.all([
    prisma.dietRecord.create({
      data: {
        userId: null,
        recordType: "food_catalog",
        type: "food_catalog",
        foodName: "Oatmeal",
        calories: 389,
        proteinGrams: 16.90,
        fatGrams: 6.90,
        carbGrams: 66.30,
        quantityGrams: 100,
        recordDate: daysAgo(0),
      },
    }),
    prisma.dietRecord.create({
      data: {
        userId: null,
        recordType: "food_catalog",
        type: "food_catalog",
        foodName: "Chicken Breast",
        calories: 165,
        proteinGrams: 31.00,
        fatGrams: 3.60,
        carbGrams: 0,
        quantityGrams: 100,
        recordDate: daysAgo(0),
      },
    }),
    prisma.dietRecord.create({
      data: {
        userId: null,
        recordType: "food_catalog",
        type: "food_catalog",
        foodName: "Apple",
        calories: 52,
        proteinGrams: 0.30,
        fatGrams: 0.20,
        carbGrams: 14.00,
        quantityGrams: 100,
        recordDate: daysAgo(0),
      },
    }),
  ]);

  for (let index = 0; index < demoDays; index++) {
    const mealDate = daysAgo(demoDays - 1 - index);
    const meal = await prisma.dietRecord.create({
      data: {
        userId: user.id,
        recordType: "meal",
        type: index % 2 === 0 ? "breakfast" : "lunch",
        mealType: index % 2 === 0 ? "breakfast" : "lunch",
        calories: 0,
        recordDate: mealDate,
        notes: "demo meal data",
      },
    });

    const secondFood = index % 2 === 0 ? foods[2] : foods[1];
    await prisma.dietRecord.createMany({
      data: [
        {
          userId: user.id,
          parentRecordId: meal.id,
          recordType: "meal_item",
          type: "meal_item",
          foodName: foods[0].foodName,
          quantityGrams: 60,
          calories: 233,
          proteinGrams: 10.14,
          fatGrams: 4.14,
          carbGrams: 39.78,
          recordDate: mealDate,
          metadata: { source: "seed", foodId: foods[0].id },
        },
        {
          userId: user.id,
          parentRecordId: meal.id,
          recordType: "meal_item",
          type: "meal_item",
          foodName: secondFood.foodName,
          quantityGrams: index % 2 === 0 ? 180 : 150,
          calories: index % 2 === 0 ? 94 : 248,
          proteinGrams: index % 2 === 0 ? 0.54 : 46.50,
          fatGrams: index % 2 === 0 ? 0.36 : 5.40,
          carbGrams: index % 2 === 0 ? 25.20 : 0,
          recordDate: mealDate,
          metadata: { source: "seed", foodId: secondFood.id },
        },
      ],
    });
  }

  await prisma.workRecord.deleteMany({ where: { userId: user.id } });
  await prisma.workRecord.create({
    data: {
      userId: user.id,
      recordType: "settings",
      recordDate: daysAgo(0),
      settings: {
        occupation: "it",
        pomodoroDuration: 25,
        sedentaryReminderOn: true,
        sedentaryInterval: 60,
        wristHealthScore: 0,
        eyeRestCount: 0,
        waterIntake: 0,
        backRelaxCount: 0,
      },
    },
  });
}

main()
  .finally(async () => {
    await prisma.$disconnect();
  })
  .catch(async (error) => {
    console.error(error);
    await prisma.$disconnect();
    process.exit(1);
  });
