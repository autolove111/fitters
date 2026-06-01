import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { addDays, formatDate, todayUtc } from "../../utils/dates.js";

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

const defaultSettings = {
  occupation: null,
  pomodoroDuration: 25,
  sedentaryReminderOn: true,
  sedentaryInterval: 60,
  wristHealthScore: 0,
  eyeRestCount: 0,
  waterIntake: 0,
  backRelaxCount: 0,
  vocalRestCount: 0,
  stopMoveCount: 0,
  eyeExerciseCount: 0,
  classBreakCount: 0,
  deepBreathCount: 0,
  legMoveCount: 0,
  neckRelaxCount: 0,
  stepCount: 0,
  energySnackCount: 0,
  standCount: 0,
};

function settingsObject(record: any): Record<string, any> {
  return { ...defaultSettings, ...(record?.settings && typeof record.settings === "object" ? record.settings : {}) };
}

function serializeSettings(record: any) {
  return {
    id: record.id,
    userId: record.userId,
    ...settingsObject(record),
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
  };
}

function serializeSession(record: any) {
  return {
    id: record.id,
    userId: record.userId,
    type: record.type,
    startTime: record.startTime,
    endTime: record.endTime,
    duration: record.durationMinutes || 0,
    durationMinutes: record.durationMinutes || 0,
    createdAt: record.createdAt,
  };
}

function serializeTodo(record: any) {
  return {
    id: record.id,
    userId: record.userId,
    content: record.content,
    completed: record.completed,
    todoDate: record.recordDate,
    createdAt: record.createdAt,
  };
}

async function getOrCreateSettings(userId: number) {
  const existing = await prisma.workRecord.findFirst({
    where: { userId, recordType: "settings" },
  });
  if (existing) return existing;
  return prisma.workRecord.create({
    data: {
      userId,
      recordType: "settings",
      recordDate: todayUtc(),
      settings: defaultSettings,
    },
  });
}

workRouter.use(requireAuth);

workRouter.get("/settings", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const settings = await getOrCreateSettings(userId);
  ok(res, serializeSettings(settings));
}));

workRouter.put("/settings", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const body = workSettingsSchema.parse(req.body);
  const current = await getOrCreateSettings(userId);

  const settings = await prisma.workRecord.update({
    where: { id: current.id },
    data: { settings: { ...settingsObject(current), ...body } },
  });

  ok(res, serializeSettings(settings));
}));

workRouter.post("/session/start", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { type, startTime } = req.body as { type?: string; startTime: string };
  const parsedStartTime = new Date(startTime);

  const session = await prisma.workRecord.create({
    data: {
      userId,
      recordType: "session",
      type: type || "pomodoro",
      recordDate: todayUtc(),
      startTime: parsedStartTime,
    },
  });

  ok(res, serializeSession(session));
}));

workRouter.put("/session/end", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { sessionId, endTime, duration } = req.body as { sessionId: number; endTime: string; duration?: number };

  const session = await prisma.workRecord.findUnique({ where: { id: sessionId } });
  if (!session || session.userId !== userId || session.recordType !== "session") {
    throw new HttpError(404, "work session not found");
  }

  const updatedSession = await prisma.workRecord.update({
    where: { id: sessionId },
    data: {
      endTime: new Date(endTime),
      durationMinutes: duration || 0,
    },
  });

  ok(res, serializeSession(updatedSession));
}));

workRouter.get("/stats/daily", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const tomorrow = addDays(today, 1);

  const sessions = await prisma.workRecord.findMany({
    where: {
      userId,
      recordType: "session",
      startTime: { gte: today, lt: tomorrow },
    },
  });

  const totalMinutes = sessions.reduce((sum, s) => sum + (s.durationMinutes || 0), 0);
  const sessionCount = sessions.length;

  ok(res, { totalMinutes, sessionCount, sessions: sessions.map(serializeSession) });
}));

workRouter.get("/stats/weekly", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const end = todayUtc();
  const start = addDays(end, -6);

  const sessions = await prisma.workRecord.findMany({
    where: {
      userId,
      recordType: "session",
      startTime: { gte: start, lt: addDays(end, 1) },
    },
  });

  const byDate: Record<string, { minutes: number; count: number }> = {};
  for (let i = 0; i < 7; i++) {
    const date = formatDate(addDays(start, i));
    byDate[date] = { minutes: 0, count: 0 };
  }

  for (const session of sessions) {
    if (!session.startTime) continue;
    const date = formatDate(session.startTime);
    if (byDate[date]) {
      byDate[date].minutes += session.durationMinutes || 0;
      byDate[date].count += 1;
    }
  }

  ok(res, Object.entries(byDate).map(([date, stats]) => ({ date, ...stats })));
}));

workRouter.post("/sedentary/respond", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const now = new Date();

  await prisma.workRecord.create({
    data: {
      userId,
      recordType: "sedentary_response",
      recordDate: todayUtc(),
      startTime: now,
      metadata: { respondedAt: now.toISOString() },
    },
  });

  ok(res, { success: true });
}));

workRouter.get("/exercises", asyncHandler(async (_req, res) => {
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
    { id: 2, name: "眼部放松", duration: 3, description: "20-20-20 法则，缓解用眼疲劳" },
    { id: 3, name: "颈部拉伸", duration: 3, description: "左右各拉伸 30 秒" },
    { id: 4, name: "肩部放松", duration: 3, description: "耸肩后放松，重复 10 次" },
    { id: 5, name: "背部伸展", duration: 5, description: "站立，双手背后交叉并向后伸展" },
  ];

  if (occupation === "it" || occupation === "writer" || occupation === "designer") {
    ok(res, exercises.filter(e => [1, 2, 3, 4].includes(e.id)));
  } else if (occupation === "driver") {
    ok(res, exercises.filter(e => [5].includes(e.id)));
  } else {
    ok(res, exercises);
  }
}));

workRouter.get("/health-data", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const settings = settingsObject(await getOrCreateSettings(userId));

  ok(res, {
    wristHealthScore: settings.wristHealthScore || 0,
    eyeRestCount: settings.eyeRestCount || 0,
    waterIntake: settings.waterIntake || 0,
    backRelaxCount: settings.backRelaxCount || 0,
  });
}));

workRouter.post("/health-data/metric", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { metricName, increment } = req.body as { metricName: string; increment?: number };
  const current = await getOrCreateSettings(userId);
  const settings = settingsObject(current);
  const currentValue = Number(settings[metricName] || 0);
  const newValue = currentValue + (increment || 1);

  const updated = await prisma.workRecord.update({
    where: { id: current.id },
    data: { settings: { ...settings, [metricName]: newValue } },
  });

  ok(res, { success: true, newValue, settings: serializeSettings(updated) });
}));

workRouter.get("/today-duration", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const tomorrow = addDays(today, 1);

  const sessions = await prisma.workRecord.findMany({
    where: {
      userId,
      recordType: "session",
      startTime: { gte: today, lt: tomorrow },
    },
  });

  const totalMinutes = sessions.reduce((sum, s) => sum + (s.durationMinutes || 0), 0);
  ok(res, { totalMinutes });
}));

workRouter.get("/todos/today", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();

  const todos = await prisma.workRecord.findMany({
    where: {
      userId,
      recordType: "todo",
      recordDate: today,
    },
    orderBy: { createdAt: "asc" },
  });

  ok(res, todos.map(serializeTodo));
}));

workRouter.post("/todos", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { content } = req.body as { content: string };

  const todo = await prisma.workRecord.create({
    data: {
      userId,
      recordType: "todo",
      recordDate: todayUtc(),
      content,
    },
  });

  ok(res, serializeTodo(todo));
}));

workRouter.delete("/todos/:todoId", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const todoId = parseInt(req.params.todoId);

  await prisma.workRecord.deleteMany({
    where: { id: todoId, userId, recordType: "todo" },
  });

  ok(res, { success: true });
}));
