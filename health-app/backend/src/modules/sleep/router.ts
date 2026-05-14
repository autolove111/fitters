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

function serializeSleep(record: any) {
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
    const { date } = req.query;
    
    const where: any = { userId };
    if (date) {
      where.recordDate = {
        gte: new Date(String(date)),
        lt: new Date(new Date(String(date)).getTime() + 24 * 60 * 60 * 1000),
      };
    }
    
    const records = await prisma.sleepRecord.findMany({
      where,
      orderBy: [{ createdAt: "desc" }],
    });
    ok(res, records.map(serializeSleep));
  }),
);

sleepRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid sleep record id");
    }
    
    const record = await prisma.sleepRecord.findUnique({ where: { id } });
    if (!record) {
      throw new HttpError(404, "sleep record not found");
    }
    
    if (record.userId !== userId) {
      throw new HttpError(403, "cannot access another user's sleep record");
    }
    
    ok(res, serializeSleep(record));
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

sleepRouter.put(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid sleep record id");
    }
    
    const record = await prisma.sleepRecord.findUnique({ where: { id } });
    if (!record) {
      throw new HttpError(404, "sleep record not found");
    }
    
    if (record.userId !== userId) {
      throw new HttpError(403, "cannot modify another user's sleep record");
    }
    
    const body = sleepSchema.partial().parse(req.body);
    
    const data: any = {};
    if (body.sleepTime) {
      data.sleepTime = new Date(body.sleepTime);
    }
    if (body.wakeTime) {
      data.wakeTime = new Date(body.wakeTime);
    }
    if (body.quality !== undefined) {
      data.quality = body.quality;
    }
    if (body.notes !== undefined) {
      data.notes = body.notes;
    }
    
    const updatedRecord = await prisma.sleepRecord.update({
      where: { id },
      data,
    });
    
    ok(res, serializeSleep(updatedRecord), "updated");
  }),
);

sleepRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid sleep record id");
    }
    
    const record = await prisma.sleepRecord.findUnique({ where: { id } });
    if (!record) {
      throw new HttpError(404, "sleep record not found");
    }
    
    if (record.userId !== userId) {
      throw new HttpError(403, "cannot delete another user's sleep record");
    }
    
    await prisma.sleepRecord.delete({ where: { id } });
    ok(res, null, "deleted");
  }),
);
