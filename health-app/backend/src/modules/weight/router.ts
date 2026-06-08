import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { todayUtc, formatDate } from "../../utils/dates.js";

export const weightRouter = Router();

const weightSchema = z.object({
  weightKg: z.number().positive(),
  recordDate: z.string().optional(),
});

function serializeWeight(record: any) {
  return {
    id: record.id,
    userId: record.userId,
    weightKg: Number(record.weightKg),
    recordDate: formatDate(record.recordDate),
    notes: record.notes,
    createdAt: record.createdAt.toISOString(),
  };
}

weightRouter.use(requireAuth);

weightRouter.get("/today", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();

  const record = await prisma.weightRecord.findFirst({
    where: { userId, recordDate: today },
    orderBy: { createdAt: "desc" },
  });

  ok(res, record ? serializeWeight(record) : null);
}));

weightRouter.post("/", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const body = weightSchema.parse(req.body);

  const record = await prisma.weightRecord.create({
    data: {
      userId,
      weightKg: body.weightKg,
      recordDate: body.recordDate ? new Date(body.recordDate) : todayUtc(),
    },
  });

  ok(res, serializeWeight(record), "created");
}));
