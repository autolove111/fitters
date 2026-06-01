import bcrypt from "bcryptjs";
import { GoalPeriod, GoalType, PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

function daysAgo(days: number) {
  const date = new Date();
  date.setUTCHours(0, 0, 0, 0);
  date.setUTCDate(date.getUTCDate() - days);
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
      notes: "demo seed data",
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
        sleepTime: new Date(daysAgo(days + 1).getTime() + 23 * 60 * 60 * 1000 + (index % 2 === 0 ? 10 : 35) * 60 * 1000),
        wakeTime: new Date(daysAgo(days).getTime() + 6 * 60 * 60 * 1000 + (30 + (index % 3) * 10) * 60 * 1000),
        quality: Math.min(100, 72 + index * 3),
        notes: "demo sleep data",
        metadata: { source: "seed" },
      };
    }),
  });

  await prisma.dietRecord.deleteMany({ where: { userId: user.id } });

  const foods = [
    { name: "Oatmeal", calories: 389, protein: 16.9, fat: 6.9, carb: 66.3 },
    { name: "Chicken Breast", calories: 165, protein: 31.0, fat: 3.6, carb: 0 },
    { name: "Apple", calories: 52, protein: 0.3, fat: 0.2, carb: 14.0 },
  ];

  const mealTypes = ["BREAKFAST", "LUNCH", "DINNER"];

  const dietData: any[] = [];
  Array.from({ length: 7 }, (_, dayIndex) => {
    const recordDate = daysAgo(6 - dayIndex);
    mealTypes.forEach((mealType, mealIndex) => {
      const food = foods[(dayIndex + mealIndex) % 3];
      const quantityGrams = 100 + dayIndex * 20 + mealIndex * 10;
      const factor = quantityGrams / 100;

      dietData.push({
        userId: user.id,
        recordDate,
        mealType,
        foodName: food.name,
        quantityGrams,
        calories: Math.round(food.calories * factor),
        proteinGrams: Number((food.protein * factor).toFixed(2)),
        fatGrams: Number((food.fat * factor).toFixed(2)),
        carbGrams: Number((food.carb * factor).toFixed(2)),
        notes: "demo diet data",
        metadata: { source: "seed" },
      });
    });
  });

  await prisma.dietRecord.createMany({ data: dietData });

  await prisma.workRecord.deleteMany({ where: { userId: user.id } });
  await prisma.workRecord.createMany({
    data: {
      userId: user.id,
      recordType: "SETTINGS",
      recordDate: daysAgo(0),
      occupation: "it",
      pomodoroDuration: 25,
      sedentaryReminderOn: true,
      sedentaryInterval: 60,
      wristHealthScore: 80,
      eyeRestCount: 3,
      waterIntake: 5,
      backRelaxCount: 2,
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
