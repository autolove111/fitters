import { Router } from "express";
import { z } from "zod";
import { asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { formatDate, todayUtc, addDays } from "../../utils/dates.js";

export const workRouter = Router();

const workSettingsSchema = z.object({
  occupation: z.string().optional(),
  pomodoroDuration: z.number().optional(),
  sedentaryReminderOn: z.boolean().optional(),
  sedentaryInterval: z.number().optional(),
  wristHealthScore: z.number().optional(),
  eyeRestCount: z.number().optional(),
  waterIntake: z.number().optional(),
  backRelaxCount: z.number().optional(),
});

workRouter.use(requireAuth);

workRouter.get("/settings", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const settings = await prisma.workSettings.findUnique({
    where: { userId },
  });

  if (!settings) {
    const defaultSettings = await prisma.workSettings.create({
      data: { userId },
    });
    return ok(res, defaultSettings);
  }

  ok(res, settings);
}));

workRouter.put("/settings", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const body = workSettingsSchema.parse(req.body);

  const settings = await prisma.workSettings.upsert({
    where: { userId },
    update: body,
    create: { userId, ...body },
  });

  ok(res, settings);
}));

workRouter.post("/session/start", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { type, startTime } = req.body;

  const session = await prisma.workSession.create({
    data: {
      userId,
      type: type || "pomodoro",
      startTime: new Date(startTime),
    },
  });

  ok(res, session);
}));

workRouter.put("/session/end", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { sessionId, endTime, duration } = req.body;

  const session = await prisma.workSession.update({
    where: { id: sessionId },
    data: {
      endTime: new Date(endTime),
      duration: duration || 0,
    },
  });

  ok(res, session);
}));

workRouter.get("/stats/daily", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const tomorrow = addDays(today, 1);

  const sessions = await prisma.workSession.findMany({
    where: {
      userId,
      startTime: { gte: today, lt: tomorrow },
    },
  });

  const totalMinutes = sessions.reduce((sum, s) => sum + (s.duration || 0), 0);
  const sessionCount = sessions.length;

  ok(res, { totalMinutes, sessionCount, sessions });
}));

workRouter.get("/stats/weekly", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const end = todayUtc();
  const start = addDays(end, -6);

  const sessions = await prisma.workSession.findMany({
    where: {
      userId,
      startTime: { gte: start, lt: addDays(end, 1) },
    },
  });

  const byDate: Record<string, { minutes: number; count: number }> = {};
  for (let i = 0; i < 7; i++) {
    const date = formatDate(addDays(start, i));
    byDate[date] = { minutes: 0, count: 0 };
  }

  for (const session of sessions) {
    const date = formatDate(session.startTime);
    if (byDate[date]) {
      byDate[date].minutes += session.duration || 0;
      byDate[date].count += 1;
    }
  }

  ok(res, Object.entries(byDate).map(([date, stats]) => ({ date, ...stats })));
}));

workRouter.post("/sedentary/respond", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;

  await prisma.sedentaryResponse.create({
    data: { userId },
  });

  ok(res, { success: true });
}));

workRouter.get("/exercises", asyncHandler(async (req, res) => {
  const exercises = [
    { id: 1, name: "手腕旋转", duration: 2, targetOccupations: ["it", "writer"] },
    { id: 2, name: "眼部放松", duration: 3, targetOccupations: ["it", "writer", "designer"] },
    { id: 3, name: "颈部拉伸", duration: 3, targetOccupations: ["it", "writer", "teacher"] },
    { id: 4, name: "肩部放松", duration: 3, targetOccupations: ["it", "writer", "designer", "teacher"] },
    { id: 5, name: "背部伸展", duration: 5, targetOccupations: ["driver", "teacher", "it"] },
    { id: 6, name: "腿部活动", duration: 5, targetOccupations: ["driver", "office_worker"] },
    { id: 7, name: "站立休息", duration: 10, targetOccupations: ["driver", "it", "writer"] },
  ];

  ok(res, exercises);
}));

workRouter.get("/exercises/recommended", asyncHandler(async (req, res) => {
  const occupation = req.query.occupation as string;
  const exercises = [
    { id: 1, name: "手腕旋转", duration: 2, description: "缓解手腕疲劳" },
    { id: 2, name: "眼部放松", duration: 3, description: "20-20-20法则：每20分钟看20英尺外的物体20秒" },
    { id: 3, name: "颈部拉伸", duration: 3, description: "左右各拉伸10秒" },
    { id: 4, name: "肩部放松", duration: 3, description: "耸肩后放松，重复10次" },
    { id: 5, name: "背部伸展", duration: 5, description: "站立，双手背后交叉，向后仰视" },
  ];

  if (occupation === "it" || occupation === "writer" || occupation === "designer") {
    ok(res, exercises.filter(e => [1, 2, 3, 4].includes(e.id)));
  } else if (occupation === "driver") {
    ok(res, exercises.filter(e => [5, 6, 7].includes(e.id)));
  } else {
    ok(res, exercises);
  }
}));

workRouter.get("/health-data", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const occupation = req.query.occupation as string;

  const settings = await prisma.workSettings.findUnique({
    where: { userId },
  });

  ok(res, {
    wristHealthScore: settings?.wristHealthScore || 0,
    eyeRestCount: settings?.eyeRestCount || 0,
    waterIntake: settings?.waterIntake || 0,
    backRelaxCount: settings?.backRelaxCount || 0,
  });
}));

workRouter.post("/health-data/metric", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { metricName, increment } = req.body;

  const settings = await prisma.workSettings.upsert({
    where: { userId },
    create: { userId },
    update: {},
  });

  let currentValue = 0;
  if (metricName === "wristHealthScore") currentValue = settings.wristHealthScore || 0;
  else if (metricName === "eyeRestCount") currentValue = settings.eyeRestCount || 0;
  else if (metricName === "waterIntake") currentValue = settings.waterIntake || 0;
  else if (metricName === "backRelaxCount") currentValue = settings.backRelaxCount || 0;
  else if (metricName === "vocalRestCount") currentValue = settings.vocalRestCount || 0;
  else if (metricName === "stopMoveCount") currentValue = settings.stopMoveCount || 0;
  else if (metricName === "eyeExerciseCount") currentValue = settings.eyeExerciseCount || 0;
  else if (metricName === "classBreakCount") currentValue = settings.classBreakCount || 0;
  else if (metricName === "deepBreathCount") currentValue = settings.deepBreathCount || 0;
  else if (metricName === "legMoveCount") currentValue = settings.legMoveCount || 0;
  else if (metricName === "neckRelaxCount") currentValue = settings.neckRelaxCount || 0;
  else if (metricName === "stepCount") currentValue = settings.stepCount || 0;
  else if (metricName === "energySnackCount") currentValue = settings.energySnackCount || 0;
  else if (metricName === "standCount") currentValue = settings.standCount || 0;

  const newValue = currentValue + (increment || 1);

  const updateData: Record<string, number> = {};
  if (metricName === "wristHealthScore") updateData.wristHealthScore = newValue;
  else if (metricName === "eyeRestCount") updateData.eyeRestCount = newValue;
  else if (metricName === "waterIntake") updateData.waterIntake = newValue;
  else if (metricName === "backRelaxCount") updateData.backRelaxCount = newValue;
  else if (metricName === "vocalRestCount") updateData.vocalRestCount = newValue;
  else if (metricName === "stopMoveCount") updateData.stopMoveCount = newValue;
  else if (metricName === "eyeExerciseCount") updateData.eyeExerciseCount = newValue;
  else if (metricName === "classBreakCount") updateData.classBreakCount = newValue;
  else if (metricName === "deepBreathCount") updateData.deepBreathCount = newValue;
  else if (metricName === "legMoveCount") updateData.legMoveCount = newValue;
  else if (metricName === "neckRelaxCount") updateData.neckRelaxCount = newValue;
  else if (metricName === "stepCount") updateData.stepCount = newValue;
  else if (metricName === "energySnackCount") updateData.energySnackCount = newValue;
  else if (metricName === "standCount") updateData.standCount = newValue;

  await prisma.workSettings.update({
    where: { userId },
    data: updateData,
  });

  ok(res, { success: true, newValue });
}));

workRouter.get("/today-duration", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const tomorrow = addDays(today, 1);

  const sessions = await prisma.workSession.findMany({
    where: {
      userId,
      startTime: { gte: today, lt: tomorrow },
    },
  });

  const totalMinutes = sessions.reduce((sum, s) => sum + (s.duration || 0), 0);
  ok(res, { totalMinutes });
}));

workRouter.get("/todos/today", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const tomorrow = addDays(today, 1);

  const todos = await prisma.workTodo.findMany({
    where: {
      userId,
      todoDate: { gte: today, lt: tomorrow },
    },
    orderBy: { createdAt: "asc" },
  });

  ok(res, todos);
}));

workRouter.post("/todos", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { content } = req.body;

  const todo = await prisma.workTodo.create({
    data: {
      userId,
      content,
      todoDate: todayUtc(),
    },
  });

  ok(res, todo);
}));

workRouter.delete("/todos/:todoId", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const todoId = parseInt(req.params.todoId);

  await prisma.workTodo.delete({
    where: { id: todoId, userId },
  });

  ok(res, { success: true });
}));