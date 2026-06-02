import bcrypt from "bcryptjs";
import { GoalPeriod, GoalType, PrismaClient } from "@prisma/client";

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
  await prisma.workoutRecord.createMany({
    data: Array.from({ length: 7 }, (_, index) => ({
      userId: user.id,
      type: index % 2 === 0 ? "running" : "cycling",
      durationMinutes: 20 + index * 5,
      calories: 120 + index * 30,
      recordDate: daysAgo(6 - index),
      sourceType: "MANUAL",
      notes: "demo seed data",
    })),
  });
  await prisma.workoutRecord.createMany({
    data: Array.from({ length: 7 }, (_, index) => ({
      userId: user.id,
      type: "wechat_steps",
      durationMinutes: 0,
      calories: 0,
      steps: 5000 + index * 650,
      sourceType: "WECHAT_WERUN",
      recordDate: daysAgo(6 - index),
      notes: "demo wechat steps",
    })),
  });

  await prisma.sleepRecord.deleteMany({ where: { userId: user.id } });
  await prisma.sleepRecord.createMany({
    data: Array.from({ length: 7 }, (_, index) => {
      const days = 6 - index;
      const durationHours = 6.8 + index * 0.15;
      return {
        userId: user.id,
        recordDate: daysAgo(days),
        durationHours,
        deepHours: 1.6 + index * 0.08,
        sleepTime: atUtc(days + 1, 23, index % 2 === 0 ? 10 : 35),
        wakeTime: atUtc(days, 6, 30 + (index % 3) * 10),
        quality: Math.min(100, 72 + index * 3),
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
    data: Array.from({ length: 7 }, (_, index) => ({
      userId: user.id,
      recordType: "diet",
      type: index % 2 === 0 ? "balanced" : "high-protein",
      calories: 1780 + index * 45,
      recordDate: daysAgo(6 - index),
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

  for (let index = 0; index < 7; index++) {
    const mealDate = daysAgo(6 - index);
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
