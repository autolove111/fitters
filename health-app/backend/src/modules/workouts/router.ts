import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { dateOnly, formatDate } from "../../utils/dates.js";

export const workoutsRouter = Router();

const workoutSchema = z.object({
  type: z.string().trim().min(1).max(64),
  durationMin: z.number().int().positive().optional(),
  durationMinutes: z.number().int().positive().optional(),
  calories: z.number().int().min(0).default(0),
  recordDate: z.string().optional(),
  date: z.string().optional(),
  notes: z.string().trim().max(255).optional(),
});

function serializeWorkout(record: {
  id: number;
  type: string;
  durationMinutes: number;
  calories: number;
  recordDate: Date;
  notes: string | null;
  createdAt: Date;
}) {
  const date = formatDate(record.recordDate);
  return {
    id: record.id,
    type: record.type,
    durationMin: record.durationMinutes,
    durationMinutes: record.durationMinutes,
    calories: record.calories,
    recordDate: date,
    date,
    notes: record.notes,
    createdAt: record.createdAt.toISOString(),
  };
}

workoutsRouter.use(requireAuth);

workoutsRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const records = await prisma.workoutRecord.findMany({
      where: { userId },
      orderBy: [{ recordDate: "desc" }, { createdAt: "desc" }],
    });
    ok(res, records.map(serializeWorkout));
  }),
);

workoutsRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = workoutSchema.parse(req.body);
    const durationMinutes = body.durationMin ?? body.durationMinutes;
    const recordDate = body.recordDate || body.date;

    if (!durationMinutes) {
      throw new HttpError(400, "durationMin is required");
    }
    if (!recordDate) {
      throw new HttpError(400, "recordDate is required");
    }

    const record = await prisma.workoutRecord.create({
      data: {
        userId,
        type: body.type,
        durationMinutes,
        calories: body.calories,
        recordDate: dateOnly(recordDate),
        notes: body.notes,
      },
    });
    ok(res, serializeWorkout(record), "created");
  }),
);

workoutsRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid workout id");
    }

    const record = await prisma.workoutRecord.findUnique({ where: { id } });
    if (!record) {
      throw new HttpError(404, "workout not found");
    }
    if (record.userId !== userId) {
      throw new HttpError(403, "cannot delete another user's workout");
    }

    await prisma.workoutRecord.delete({ where: { id } });
    ok(res, null, "deleted");
  }),
);
