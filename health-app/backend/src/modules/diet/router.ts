import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { dateOnly, formatDate } from "../../utils/dates.js";

export const dietRouter = Router();

const dietSchema = z.object({
  type: z.string().trim().min(1).max(64),
  calories: z.number().int().min(0).default(0),
  recordDate: z.string().optional(),
  date: z.string().optional(),
  notes: z.string().trim().max(255).optional(),
});

function serializeDiet(record: {
  id: number;
  type: string;
  calories: number;
  recordDate: Date;
  notes: string | null;
  createdAt: Date;
}) {
  const date = formatDate(record.recordDate);
  return {
    id: record.id,
    type: record.type,
    calories: record.calories,
    recordDate: date,
    date,
    notes: record.notes,
    createdAt: record.createdAt.toISOString(),
  };
}

dietRouter.use(requireAuth);

dietRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const records = await prisma.dietRecord.findMany({
      where: { userId },
      orderBy: [{ recordDate: "desc" }, { createdAt: "desc" }],
    });
    ok(res, records.map(serializeDiet));
  }),
);

dietRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = dietSchema.parse(req.body);
    const recordDate = body.recordDate || body.date;

    if (!recordDate) {
      throw new HttpError(400, "recordDate is required");
    }

    const record = await prisma.dietRecord.create({
      data: {
        userId,
        type: body.type,
        calories: body.calories,
        recordDate: dateOnly(recordDate),
        notes: body.notes,
      },
    });
    ok(res, serializeDiet(record), "created");
  }),
);
