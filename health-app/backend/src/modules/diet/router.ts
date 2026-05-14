import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { dateOnly, formatDate } from "../../utils/dates.js";

export const dietRouter = Router();

const dietSchema = z.object({
  type: z.string().trim().min(1).max(64).optional(),
  foodName: z.string().trim().min(1).max(64).optional(),
  calories: z.number().int().min(0).default(0),
  recordDate: z.string().optional(),
  date: z.string().optional(),
  notes: z.string().trim().max(255).optional(),
});

function serializeDiet(record: any) {
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
    const { date, type } = req.query;
    
    const where: any = { userId };
    if (date) {
      where.recordDate = dateOnly(String(date));
    }
    if (type) {
      where.type = String(type);
    }
    
    const records = await prisma.dietRecord.findMany({
      where,
      orderBy: [{ recordDate: "desc" }, { createdAt: "desc" }],
    });
    ok(res, records.map(serializeDiet));
  }),
);

dietRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid diet record id");
    }
    
    const record = await prisma.dietRecord.findUnique({ where: { id } });
    if (!record) {
      throw new HttpError(404, "diet record not found");
    }
    
    if (record.userId !== userId) {
      throw new HttpError(403, "cannot access another user's diet record");
    }
    
    ok(res, serializeDiet(record));
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

    const type = body.type || body.foodName;
    if (!type) {
      throw new HttpError(400, "type or foodName is required");
    }

    const record = await prisma.dietRecord.create({
      data: {
        userId,
        type,
        calories: body.calories,
        recordDate: dateOnly(recordDate),
        notes: body.notes,
      },
    });
    ok(res, serializeDiet(record), "created");
  }),
);

dietRouter.put(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid diet record id");
    }
    
    const record = await prisma.dietRecord.findUnique({ where: { id } });
    if (!record) {
      throw new HttpError(404, "diet record not found");
    }
    
    if (record.userId !== userId) {
      throw new HttpError(403, "cannot modify another user's diet record");
    }
    
    const body = dietSchema.partial().parse(req.body);
    
    const data: any = {};
    if (body.type) {
      data.type = body.type;
    }
    if (body.calories !== undefined) {
      data.calories = body.calories;
    }
    if (body.recordDate || body.date) {
      data.recordDate = dateOnly(body.recordDate || body.date || "");
    }
    if (body.notes !== undefined) {
      data.notes = body.notes;
    }
    
    const updatedRecord = await prisma.dietRecord.update({
      where: { id },
      data,
    });
    
    ok(res, serializeDiet(updatedRecord), "updated");
  }),
);

dietRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid diet record id");
    }
    
    const record = await prisma.dietRecord.findUnique({ where: { id } });
    if (!record) {
      throw new HttpError(404, "diet record not found");
    }
    
    if (record.userId !== userId) {
      throw new HttpError(403, "cannot delete another user's diet record");
    }
    
    await prisma.dietRecord.delete({ where: { id } });
    ok(res, null, "deleted");
  }),
);
