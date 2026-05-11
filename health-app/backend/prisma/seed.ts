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
        sleepTime: atUtc(days + 1, 23, index % 2 === 0 ? 10 : 35),
        wakeTime: atUtc(days, 6, 30 + (index % 3) * 10),
        quality: Math.min(100, 72 + index * 3),
        notes: "demo sleep data",
        metadata: { source: "seed" },
      };
    }),
  });

  await prisma.dietRecord.deleteMany({ where: { userId: user.id } });
  await prisma.dietRecord.createMany({
    data: Array.from({ length: 7 }, (_, index) => ({
      userId: user.id,
      type: index % 2 === 0 ? "balanced" : "high-protein",
      calories: 1780 + index * 45,
      recordDate: daysAgo(6 - index),
      notes: "demo diet summary data",
    })),
  });

  const foods = await Promise.all([
    prisma.food.upsert({
      where: { name: "Oatmeal" },
      update: {},
      create: {
        name: "Oatmeal",
        caloriesKcal: 389,
        proteinGrams: 16.90,
        fatGrams: 6.90,
        carbGrams: 66.30,
        servingGrams: 100,
      },
    }),
    prisma.food.upsert({
      where: { name: "Chicken Breast" },
      update: {},
      create: {
        name: "Chicken Breast",
        caloriesKcal: 165,
        proteinGrams: 31.00,
        fatGrams: 3.60,
        carbGrams: 0,
        servingGrams: 100,
      },
    }),
    prisma.food.upsert({
      where: { name: "Apple" },
      update: {},
      create: {
        name: "Apple",
        caloriesKcal: 52,
        proteinGrams: 0.30,
        fatGrams: 0.20,
        carbGrams: 14.00,
        servingGrams: 100,
      },
    }),
  ]);

  await prisma.mealItem.deleteMany({ where: { meal: { userId: user.id } } });
  await prisma.meal.deleteMany({ where: { userId: user.id } });
  await Promise.all(
    Array.from({ length: 7 }, (_, index) => {
      const mealDate = daysAgo(6 - index);
      return prisma.meal.create({
        data: {
          userId: user.id,
          mealDate,
          mealType: index % 2 === 0 ? "breakfast" : "lunch",
          notes: "demo meal data",
          items: {
            create: [
              {
                foodId: foods[0].id,
                foodName: foods[0].name,
                quantityGrams: 60,
                calories: 233,
                proteinGrams: 10.14,
                fatGrams: 4.14,
                carbGrams: 39.78,
                metadata: { source: "seed" },
              },
              {
                foodId: index % 2 === 0 ? foods[2].id : foods[1].id,
                foodName: index % 2 === 0 ? foods[2].name : foods[1].name,
                quantityGrams: index % 2 === 0 ? 180 : 150,
                calories: index % 2 === 0 ? 94 : 248,
                proteinGrams: index % 2 === 0 ? 0.54 : 46.50,
                fatGrams: index % 2 === 0 ? 0.36 : 5.40,
                carbGrams: index % 2 === 0 ? 25.20 : 0,
                metadata: { source: "seed" },
              },
            ],
          },
        },
      });
    }),
  );
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
