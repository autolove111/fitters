import { Router } from "express";
import { z } from "zod";
import { asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { formatDate, todayUtc, addDays } from "../../utils/dates.js";

export const workRouter = Router();

const workRecordSchema = z.object({
  occupation: z.string().optional(),
  pomodoroDuration: z.number().optional(),
  sedentaryReminderOn: z.boolean().optional(),
  sedentaryInterval: z.number().optional(),
  wristHealthScore: z.number().optional(),
  eyeRestCount: z.number().optional(),
  waterIntake: z.number().optional(),
  backRelaxCount: z.number().optional(),
  vocalRestCount: z.number().optional(),
  stopMoveCount: z.number().optional(),
  eyeExerciseCount: z.number().optional(),
  classBreakCount: z.number().optional(),
  deepBreathCount: z.number().optional(),
  legMoveCount: z.number().optional(),
  neckRelaxCount: z.number().optional(),
  stepCount: z.number().optional(),
  energySnackCount: z.number().optional(),
  standCount: z.number().optional(),
});

function toNumber(value: any): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'bigint') return Number(value);
  if (typeof value === 'number') return value;
  if (value.toNumber) return value.toNumber();
  return Number(value);
}

function serializeWorkRecord(record: any) {
  return {
    id: record.id,
    recordType: record.recordType,
    recordDate: formatDate(record.recordDate),
    occupation: record.occupation,
    pomodoroDuration: record.pomodoroDuration,
    sedentaryReminderOn: record.sedentaryReminderOn,
    sedentaryInterval: record.sedentaryInterval,
    wristHealthScore: record.wristHealthScore,
    eyeRestCount: record.eyeRestCount,
    waterIntake: record.waterIntake,
    backRelaxCount: record.backRelaxCount,
    vocalRestCount: record.vocalRestCount,
    stopMoveCount: record.stopMoveCount,
    eyeExerciseCount: record.eyeExerciseCount,
    classBreakCount: record.classBreakCount,
    deepBreathCount: record.deepBreathCount,
    legMoveCount: record.legMoveCount,
    neckRelaxCount: record.neckRelaxCount,
    stepCount: record.stepCount,
    energySnackCount: record.energySnackCount,
    standCount: record.standCount,
    sessionType: record.sessionType,
    sessionStart: record.sessionStart?.toISOString(),
    sessionEnd: record.sessionEnd?.toISOString(),
    sessionDuration: record.sessionDuration,
    todoContent: record.todoContent,
    todoCompleted: record.todoCompleted,
    sedentaryRespondedAt: record.sedentaryRespondedAt?.toISOString(),
    notes: record.notes,
    metadata: record.metadata,
    createdAt: record.createdAt.toISOString(),
  };
}

workRouter.use(requireAuth);

workRouter.get("/settings", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();

  const settings = await prisma.workRecord.findFirst({
    where: {
      userId,
      recordType: "SETTINGS",
      recordDate: today,
    },
  });

  if (!settings) {
    const newSettings = await prisma.workRecord.create({
      data: {
        userId,
        recordType: "SETTINGS",
        recordDate: today,
        pomodoroDuration: 25,
        sedentaryReminderOn: true,
        sedentaryInterval: 60,
      },
    });
    return ok(res, serializeWorkRecord(newSettings));
  }

  ok(res, serializeWorkRecord(settings));
}));

workRouter.put("/settings", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const body = workRecordSchema.parse(req.body);

  const existingSettings = await prisma.workRecord.findFirst({
    where: { userId, recordType: "SETTINGS", recordDate: today },
  });

  let settings;
  if (existingSettings) {
    settings = await prisma.workRecord.update({
      where: { id: existingSettings.id },
      data: body,
    });
  } else {
    settings = await prisma.workRecord.create({
      data: {
        userId,
        recordType: "SETTINGS",
        recordDate: today,
        ...body,
      },
    });
  }

  ok(res, serializeWorkRecord(settings));
}));

workRouter.post("/session/start", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { type, startTime } = req.body as { type?: string; startTime: string };
  const today = todayUtc();

  const session = await prisma.workRecord.create({
    data: {
      userId,
      recordType: "SESSION",
      recordDate: today,
      sessionType: type || "pomodoro",
      sessionStart: new Date(startTime),
    },
  });

  ok(res, serializeWorkRecord(session));
}));

workRouter.put("/session/end", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { sessionId, endTime, duration } = req.body as { sessionId: number; endTime: string; duration?: number };

  const session = await prisma.workRecord.update({
    where: { id: sessionId, userId },
    data: {
      sessionEnd: new Date(endTime),
      sessionDuration: duration || 0,
    },
  });

  ok(res, serializeWorkRecord(session));
}));

workRouter.get("/stats/daily", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const tomorrow = addDays(today, 1);

  const sessions = await prisma.workRecord.findMany({
    where: {
      userId,
      recordType: "SESSION",
      sessionStart: { gte: today, lt: tomorrow },
    },
  });

  const totalMinutes = sessions.reduce((sum, s) => sum + (s.sessionDuration || 0), 0);
  const sessionCount = sessions.length;

  ok(res, { totalMinutes, sessionCount, sessions: sessions.map(serializeWorkRecord) });
}));

workRouter.get("/stats/weekly", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const end = todayUtc();
  const start = addDays(end, -6);

  const sessions = await prisma.workRecord.findMany({
    where: {
      userId,
      recordType: "SESSION",
      sessionStart: { gte: start, lt: addDays(end, 1) },
    },
  });

  const byDate: Record<string, { minutes: number; count: number }> = {};
  for (let i = 0; i < 7; i++) {
    const date = formatDate(addDays(start, i));
    byDate[date] = { minutes: 0, count: 0 };
  }

  for (const session of sessions) {
    if (session.sessionStart) {
      const date = formatDate(session.sessionStart);
      if (byDate[date]) {
        byDate[date].minutes += session.sessionDuration || 0;
        byDate[date].count += 1;
      }
    }
  }

  ok(res, Object.entries(byDate).map(([date, stats]) => ({ date, ...stats })));
}));

workRouter.post("/sedentary/respond", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();

  const record = await prisma.workRecord.create({
    data: {
      userId,
      recordType: "RESPONSE",
      recordDate: today,
      sedentaryRespondedAt: new Date(),
    },
  });

  ok(res, serializeWorkRecord(record));
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
  const today = todayUtc();

  const healthRecord = await prisma.workRecord.findFirst({
    where: {
      userId,
      recordType: "SETTINGS",
      recordDate: today,
    },
  });

  ok(res, {
    wristHealthScore: healthRecord?.wristHealthScore || 0,
    eyeRestCount: healthRecord?.eyeRestCount || 0,
    waterIntake: healthRecord?.waterIntake || 0,
    backRelaxCount: healthRecord?.backRelaxCount || 0,
  });
}));

workRouter.post("/health-data/metric", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const { metricName, increment } = req.body as { metricName: string; increment?: number };

  let healthRecord = await prisma.workRecord.findFirst({
    where: { userId, recordType: "SETTINGS", recordDate: today },
  });

  if (!healthRecord) {
    healthRecord = await prisma.workRecord.create({
      data: {
        userId,
        recordType: "SETTINGS",
        recordDate: today,
      },
    });
  }

  const metricMap: Record<string, string> = {
    wristHealthScore: "wristHealthScore",
    eyeRestCount: "eyeRestCount",
    waterIntake: "waterIntake",
    backRelaxCount: "backRelaxCount",
    vocalRestCount: "vocalRestCount",
    stopMoveCount: "stopMoveCount",
    eyeExerciseCount: "eyeExerciseCount",
    classBreakCount: "classBreakCount",
    deepBreathCount: "deepBreathCount",
    legMoveCount: "legMoveCount",
    neckRelaxCount: "neckRelaxCount",
    stepCount: "stepCount",
    energySnackCount: "energySnackCount",
    standCount: "standCount",
  };

  const dbField = metricMap[metricName];
  if (!dbField) {
    throw new Error("invalid metric name");
  }

  const currentValue = (healthRecord as any)[dbField] || 0;
  const newValue = currentValue + (increment || 1);

  const updatedRecord = await prisma.workRecord.update({
    where: { id: healthRecord.id },
    data: { [dbField]: newValue },
  });

  ok(res, { success: true, newValue });
}));

workRouter.get("/today-duration", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const tomorrow = addDays(today, 1);

  const sessions = await prisma.workRecord.findMany({
    where: {
      userId,
      recordType: "SESSION",
      sessionStart: { gte: today, lt: tomorrow },
    },
  });

  const totalMinutes = sessions.reduce((sum, s) => sum + (s.sessionDuration || 0), 0);
  ok(res, { totalMinutes });
}));

workRouter.get("/todos/today", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();
  const tomorrow = addDays(today, 1);

  const todos = await prisma.workRecord.findMany({
    where: {
      userId,
      recordType: "TODO",
      recordDate: { gte: today, lt: tomorrow },
    },
    orderBy: { createdAt: "asc" },
  });

  ok(res, todos.map(serializeWorkRecord));
}));

workRouter.post("/todos", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const { content } = req.body as { content: string };
  const today = todayUtc();

  const todo = await prisma.workRecord.create({
    data: {
      userId,
      recordType: "TODO",
      recordDate: today,
      todoContent: content,
      todoCompleted: false,
    },
  });

  ok(res, serializeWorkRecord(todo));
}));

workRouter.delete("/todos/:todoId", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const todoId = parseInt(req.params.todoId);

  await prisma.workRecord.delete({
    where: { id: todoId, userId },
  });

  ok(res, { success: true });
}));
