import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";

export const sleepRouter = Router();

const sleepSchema = z.object({
  sleepTime: z.string().datetime(),
  wakeTime: z.string().datetime(),
  quality: z.number().int().min(0).max(10).default(0),
  notes: z.string().trim().max(255).optional(),
});

function serializeSleep(record: {
  id: number;
  sleepTime: Date;
  wakeTime: Date;
  quality: number;
  notes: string | null;
  createdAt: Date;
}) {
  return {
    id: record.id,
    sleepTime: record.sleepTime.toISOString(),
    wakeTime: record.wakeTime.toISOString(),
    quality: record.quality,
    notes: record.notes,
    createdAt: record.createdAt.toISOString(),
  };
}

sleepRouter.use(requireAuth);

sleepRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const records = await prisma.sleepRecord.findMany({
      where: { userId },
      orderBy: [{ createdAt: "desc" }],
    });
    ok(res, records.map(serializeSleep));
  }),
);

sleepRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = sleepSchema.parse(req.body);

    const record = await prisma.sleepRecord.create({
      data: {
        userId,
        sleepTime: new Date(body.sleepTime),
        wakeTime: new Date(body.wakeTime),
        quality: body.quality,
        notes: body.notes,
      },
    });
    ok(res, serializeSleep(record), "created");
  }),
);
