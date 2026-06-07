import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { todayUtc, formatDate } from "../../utils/dates.js";

export const waterRouter = Router();

const waterSchema = z.object({
  amountMl: z.number().int().positive(),
  recordDate: z.string().optional(),
});

function serializeWater(record: any) {
  return {
    id: record.id,
    userId: record.userId,
    amountMl: record.amountMl,
    recordDate: formatDate(record.recordDate),
    notes: record.notes,
    createdAt: record.createdAt.toISOString(),
  };
}

waterRouter.use(requireAuth);

waterRouter.get("/", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const records = await prisma.waterRecord.findMany({
    where: { userId },
    orderBy: { recordDate: "desc" },
  });
  ok(res, records.map(serializeWater));
}));

waterRouter.get("/today", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const today = todayUtc();

  const records = await prisma.waterRecord.findMany({
    where: { userId, recordDate: today },
    orderBy: { createdAt: "asc" },
  });

  const totalMl = records.reduce((sum, r) => sum + r.amountMl, 0);

  ok(res, {
    records: records.map(serializeWater),
    totalMl,
  });
}));

waterRouter.post("/", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const body = waterSchema.parse(req.body);

  const record = await prisma.waterRecord.create({
    data: {
      userId,
      amountMl: body.amountMl,
      recordDate: body.recordDate ? new Date(body.recordDate) : todayUtc(),
    },
  });

  ok(res, serializeWater(record), "created");
}));
