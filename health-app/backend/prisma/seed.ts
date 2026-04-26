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
